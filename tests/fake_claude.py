#!/usr/bin/env python3
"""테스트용 가짜 claude: 헤드리스 Claude Code의 `--output-format stream-json` 출력을 흉내 낸다.

이벤트 모양은 2026-10-23에 실제 claude 2.1.309에서 받은 `fixtures/stream_ok.jsonl`·`stream_denied.jsonl`을 따른다. 시나리오는 FAKE_CLAUDE_SCENARIO(JSON 파일)에서 읽는다. 키는 프롬프트의 "원래 파일 이름: …" 줄에 적힌 이름이고, "*"가 기본값이다. 호출마다 argv·cwd·프롬프트·환경 일부·pid를 FAKE_CLAUDE_CALLS(jsonl)에 남긴다.

행동 키(모두 생략 가능):
  replay        픽스처 jsonl 경로. 그 줄을 그대로 내보내고(/sandbox는 cwd로) 파일은 건드리지 않는다
  output        output.md에 쓸 글. null이면 쓰지 않는다. 기본은 짧은 글
  marker        Read 결과·Write 조각·tool_use_result·거부된 Write 입력에 섞어 넣을 표식(본문 차단 테스트)
  models        modelUsage 키 목록(기본 ["claude-opus-5-5"], []이면 비운다)
  is_error      결과의 is_error
  result_text   결과의 result 글(기본은 짧은 보고)
  exit          종료 코드
  no_result     result 이벤트를 내보내지 않는다
  stderr        stderr에 쓸 글
  deny_write    거부된 Write를 permission_denials에 넣는다
  delay         이벤트 사이 대기(초)
  silent        init 뒤 이만큼(초) 아무것도 내보내지 않는다. child_pid_file이 있으면 sleep 자식을 띄우고 그 pid를 남긴다
  rate_limited  rate_limit_event(status rejected)를 내보내고 delay만큼 기다린다
  modify        실행 도중 이 절대 경로 파일 끝에 글을 덧붙인다
  create        실행 도중 이 절대 경로에 파일을 만든다
  ignore_term   SIGTERM을 무시한다
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

DEFAULT_OUTPUT = "# 🖇️강변 마을의 변화\n\n## 🌉다리와 인구\n\n마을의 인구는 다리가 열린 뒤 두 배가 되었다.\n"


def emit(event, delay=0.0):
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)
    if delay:
        time.sleep(delay)


def stream(index, content_block):
    return {"type": "stream_event", "event": {"type": "content_block_start", "index": index, "content_block": content_block}}


def delta(index, kind, **fields):
    return {"type": "stream_event", "event": {"type": "content_block_delta", "index": index, "delta": {"type": kind, **fields}}}


def stop(index):
    return {"type": "stream_event", "event": {"type": "content_block_stop", "index": index}}


def tool_call(name, tool_input, delay):
    """content_block_start → input_json_delta 조각들 → stop → assistant 메시지."""
    tid = "toolu_" + uuid.uuid4().hex[:20]
    emit(stream(0, {"type": "tool_use", "id": tid, "name": name, "input": {}}), delay)
    raw = json.dumps(tool_input, ensure_ascii=False)
    for i in range(0, len(raw), 40):
        emit(delta(0, "input_json_delta", partial_json=raw[i:i + 40]), delay)
    emit(stop(0), delay)
    emit({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": name, "input": tool_input}]}}, delay)
    return tid


def main():
    argv = sys.argv[1:]
    prompt = sys.stdin.read()
    cwd = Path.cwd()
    calls = os.environ.get("FAKE_CLAUDE_CALLS")
    if calls:
        with open(calls, "a", encoding="utf-8") as f:
            env = {k: os.environ.get(k) for k in ("CLAUDE_CODE_MAX_OUTPUT_TOKENS",)}
            f.write(json.dumps({"argv": argv, "cwd": str(cwd), "prompt": prompt, "env": env, "pid": os.getpid()}, ensure_ascii=False) + "\n")

    scenario = {}
    if os.environ.get("FAKE_CLAUDE_SCENARIO"):
        scenarios = json.loads(Path(os.environ["FAKE_CLAUDE_SCENARIO"]).read_text(encoding="utf-8"))
        m = re.search(r"원래 파일 이름: (.+)", prompt)
        scenario = scenarios.get(m.group(1).strip() if m else "", scenarios.get("*", {}))
    b = scenario
    if b.get("ignore_term"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if b.get("stderr"):
        print(b["stderr"], file=sys.stderr, flush=True)

    if b.get("replay"):
        for line in Path(b["replay"]).read_text(encoding="utf-8").splitlines():
            print(line.replace("/sandbox", str(cwd)), flush=True)
        return b.get("exit", 0)

    delay = float(b.get("delay", 0))
    models = b["models"] if "models" in b else ["claude-opus-5-5"]
    model = models[0] if models else "claude-opus-5-5"
    emit({"type": "system", "subtype": "init", "cwd": str(cwd), "session_id": str(uuid.uuid4()), "tools": ["Read", "Write"],
          "model": model, "permissionMode": "acceptEdits"}, delay)
    emit({"type": "system", "subtype": "status", "status": "requesting"}, delay)

    if b.get("silent"):
        if b.get("child_pid_file"):
            child = subprocess.Popen(["sleep", "300"])
            Path(b["child_pid_file"]).write_text(str(child.pid))
        time.sleep(float(b["silent"]))

    marker = b.get("marker", "")
    source = cwd / "source.md"
    text = source.read_text(encoding="utf-8") if source.exists() else ""
    tid = tool_call("Read", {"file_path": str(source)}, delay)
    numbered = "".join(f"{n}\t{line}\n" for n, line in enumerate((text + marker).splitlines(), 1))
    emit({"type": "user", "message": {"content": [{"tool_use_id": tid, "type": "tool_result", "content": numbered}]},
          "tool_use_result": {"type": "text", "file": {"filePath": str(source), "content": text + marker}}}, delay)

    if b.get("rate_limited"):
        emit({"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "rateLimitType": "five_hour"}}, delay)

    emit(stream(0, {"type": "thinking", "thinking": ""}), delay)
    emit({"type": "system", "subtype": "thinking_tokens", "thinking_tokens": 120}, delay)
    emit(delta(0, "thinking_delta", thinking=""), delay)
    emit(stop(0), delay)

    if b.get("modify"):
        with open(b["modify"], "a", encoding="utf-8") as f:
            f.write("\n바뀐 문장.\n")
    if b.get("create"):
        Path(b["create"]).write_text("다른 실행이 먼저 쓴 글\n", encoding="utf-8")

    denials = []
    output = b.get("output", DEFAULT_OUTPUT)
    if b.get("deny_write"):
        content = "거부된 본문 " + marker
        tid = tool_call("Write", {"file_path": str(cwd / "output.md"), "content": content}, delay)
        emit({"type": "system", "subtype": "permission_denied", "tool_name": "Write", "tool_use_id": tid,
              "decision_reason": "fake", "message": "denied"}, delay)
        denials.append({"tool_name": "Write", "tool_use_id": tid, "tool_input": {"file_path": str(cwd / "output.md"), "content": content}})
    elif output is not None:
        content = output + marker
        tid = tool_call("Write", {"file_path": str(cwd / "output.md"), "content": content}, delay)
        (cwd / "output.md").write_text(content, encoding="utf-8")
        emit({"type": "user", "message": {"content": [{"tool_use_id": tid, "type": "tool_result", "content": "File created successfully"}]},
              "tool_use_result": {"type": "create", "filePath": str(cwd / "output.md"), "content": content}}, delay)

    emit(stream(1, {"type": "text", "text": ""}), delay)
    result_text = b.get("result_text", "output.md에 썼다.")
    emit(delta(1, "text_delta", text=result_text), delay)
    emit(stop(1), delay)
    if not b.get("no_result"):
        emit({"type": "result", "subtype": "success", "is_error": bool(b.get("is_error")), "result": result_text,
              "permission_denials": denials, "modelUsage": {m: {"outputTokens": 10, "maxOutputTokens": 128000} for m in models}})
    return int(b.get("exit", 0))


if __name__ == "__main__":
    sys.exit(main())
