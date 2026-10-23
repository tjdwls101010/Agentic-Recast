"""recast 스킬의 구조 계약: cli.py 하나와 패키지 하나, 단위 종류별 import 방향, 인터페이스 밖 접근 금지, import 경로 편집 금지.

모듈은 아직 패키지 바로 아래 평평하게 놓여 있어 모듈 하나가 곧 단위이고, 밑줄로 시작하지 않는 이름이 그 인터페이스다. 하위 패키지가 생기면 그 `__init__.py`가 인터페이스가 되도록 이 테스트를 넓힌다. 정적으로 보이는 접근(import, import한 이름에서 시작하는 속성 사슬, patch 대상 문자열)만 판정한다.
"""
import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / '.claude' / 'skills' / 'recast'
SCRIPTS = SKILL / 'scripts'
TESTS = ROOT / 'tests'
PACKAGE = 'recast'
CALL = 'uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py"'
INVOCATION = f'Bash({CALL} *)'
# 패키지 바로 아래 모듈마다 종류를 선언한다. 새 모듈은 여기 종류를 적어야 테스트를 통과한다.
KINDS = {
    'paths': 'common',
    'sources': 'common',
    'publish': 'common',
    'claude': 'system',
    'runs': 'store',
    'run': 'feature',
    'status': 'feature',
}
# 종류마다 import해도 되는 종류. feature는 자기 자신 말고 다른 feature를 import하지 않는다.
ALLOWED = {
    'common': {'common'},
    'system': {'common'},
    'store': {'common'},
    'feature': {'common', 'system', 'store'},
    'cli': {'common', 'feature'},
}
IGNORED = {'__pycache__', '.DS_Store'}


def python_files(directory):
    return sorted(p for p in directory.rglob('*.py') if '__pycache__' not in p.parts)


def module_name(path):
    parts = list(path.relative_to(SCRIPTS).with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def imported_modules(tree, current, is_package):
    """모듈이 import하는 절대 이름. 상대 import는 `current` 기준으로 푼다."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = current.split('.') if is_package else current.split('.')[:-1]
                base = base[:len(base) - node.level + 1]
                prefix = '.'.join(base + ([node.module] if node.module else []))
            else:
                prefix = node.module
            names.append(prefix)
            names += [prefix + '.' + alias.name for alias in node.names]
    return names


def path_edits(tree):
    """sys.path 변경, site.addsitedir, spec_from_file_location — 글자가 아니라 코드로 찾는다."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ('addsitedir', 'spec_from_file_location'):
            found.append(node.attr)
        elif isinstance(node, ast.Name) and node.id == 'spec_from_file_location':
            found.append(node.id)
        elif isinstance(node, ast.ImportFrom) and any(a.name in ('addsitedir', 'spec_from_file_location') for a in node.names):
            found.append(node.module)
        elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute) and node.value.attr == 'path'
              and isinstance(node.value.value, ast.Name) and node.value.value.id == 'sys'):
            found.append('sys.path.' + node.attr)
        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Subscript):
                    target = target.value
                if (isinstance(target, ast.Attribute) and target.attr == 'path'
                        and isinstance(target.value, ast.Name) and target.value.id == 'sys'):
                    found.append('sys.path =')
    return found


def pep723(source):
    """`# /// script` 블록을 TOML로 읽는다(PEP 723 참조 정규식)."""
    blocks = [m for m in re.finditer(r'(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$', source)
              if m['type'] == 'script']
    if len(blocks) != 1:
        return None
    content = ''.join(line[2:] if line.startswith('# ') else line[1:]
                      for line in blocks[0]['content'].splitlines(keepends=True))
    return tomllib.loads(content)


def skill_md():
    text = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
    front = re.match(r'---\n(.*?)\n---\n', text, re.S)
    return (front[1] if front else ''), text[front.end():] if front else text


def kind(module):
    if module == 'cli':
        return 'cli'
    parts = module.split('.')
    if len(parts) == 1:
        return 'package'
    return KINDS.get(parts[1], 'undeclared')


def skill_modules():
    modules = {module_name(p): p for p in python_files(SCRIPTS / PACKAGE)}
    modules['cli'] = SCRIPTS / 'cli.py'
    return modules


def test_scripts_holds_cli_and_one_package():
    entries = {p.name for p in SCRIPTS.iterdir()} - IGNORED
    assert entries == {'cli.py', PACKAGE}


def test_package_does_not_shadow_the_standard_library():
    assert PACKAGE not in sys.stdlib_module_names


def test_every_module_has_a_kind_and_the_package_init_is_empty():
    root = SCRIPTS / PACKAGE
    assert (root / '__init__.py').is_file()
    assert not (root / '__init__.py').read_text().strip()
    children = {p.stem if p.suffix == '.py' else p.name for p in root.iterdir()
                if p.name not in IGNORED and p.name != '__init__.py' and (p.suffix == '.py' or p.is_dir())}
    assert children == set(KINDS), f'선언과 다른 모듈: {sorted(children ^ set(KINDS))}'


def test_imports_follow_unit_kinds_without_cycles():
    modules = skill_modules()
    edges, found = {}, []
    for name, path in modules.items():
        tree = ast.parse(path.read_text(encoding='utf-8'))
        imports = imported_modules(tree, name, path.name == '__init__.py')
        edges[name] = {t for t in modules if t != name and any(i == t or i.startswith(t + '.') for i in imports)}
        edges[name] -= {t for t in edges[name] if kind(t) == 'package' and any(o.startswith(t + '.') for o in edges[name])}
    for source, targets in edges.items():
        for target in targets:
            if target == 'cli':
                found.append(f'{source}가 cli를 import한다')
            elif kind(source) == 'package' or kind(target) == 'package':
                continue
            elif kind(target) not in ALLOWED.get(kind(source), set()):
                found.append(f'{source}({kind(source)})가 {target}({kind(target)})를 import한다')
    state = {}

    def visit(module, stack):
        state[module] = 'active'
        for target in sorted(edges.get(module, ())):
            if state.get(target) == 'active':
                found.append('import 순환: ' + ' -> '.join(stack[stack.index(target):] + [target]))
            elif target not in state:
                visit(target, stack + [target])
        state[module] = 'done'

    for module in sorted(edges):
        if module not in state:
            visit(module, [module])
    assert not found


def test_nothing_edits_the_import_path():
    found = [f'{path.name}: {edit}' for path in [*skill_modules().values(), *python_files(TESTS)]
             for edit in path_edits(ast.parse(path.read_text(encoding='utf-8')))]
    assert not found


def test_tests_run_cli_as_a_process_and_never_import_it():
    found = [path.name for path in python_files(TESTS)
             if any(n == 'cli' or n.startswith('cli.') for n in imported_modules(ast.parse(path.read_text(encoding='utf-8')), 'tests', False))]
    assert not found


def private_reaches(tree, owner):
    """`owner` 밖에서 recast 모듈의 밑줄 이름에 닿는 곳. owner는 이 파일이 패키지 모듈이면 그 이름, 아니면 None."""
    bound, found = {}, []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if node.level and owner:
                module = '.'.join(owner.split('.')[:-node.level] + ([module] if module else []))
            for alias in node.names:
                full = f'{module}.{alias.name}' if module else alias.name
                if module == PACKAGE and alias.name in KINDS:
                    bound[alias.asname or alias.name] = full
                elif module.startswith(PACKAGE + '.') and alias.name.startswith('_') and module != owner:
                    found.append(full)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PACKAGE + '.') and alias.asname:
                    bound[alias.asname] = alias.name
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in bound
                and node.attr.startswith('_') and not node.attr.startswith('__') and bound[node.value.id] != owner):
            found.append(f'{bound[node.value.id]}.{node.attr}')
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            m = re.fullmatch(rf'({PACKAGE}\.\w+)\.(_\w+)', node.value)
            if m and not m[2].startswith('__') and m[1] != owner:
                found.append(node.value)
    return found


def test_nothing_outside_a_module_reaches_its_private_names():
    found = []
    for name, path in skill_modules().items():
        owner = name if name != 'cli' else None
        found += [f'{path.name}: {r}' for r in private_reaches(ast.parse(path.read_text(encoding='utf-8')), owner)]
    for path in python_files(TESTS):
        found += [f'{path.name}: {r}' for r in private_reaches(ast.parse(path.read_text(encoding='utf-8')), None)]
    assert not found


def test_cli_declares_its_python_and_dependencies_inline():
    metadata = pep723((SCRIPTS / 'cli.py').read_text(encoding='utf-8'))
    assert metadata and 'requires-python' in metadata and 'dependencies' in metadata


def test_skill_md_runs_the_cli_and_every_path_it_names_exists():
    front, body = skill_md()
    line = re.search(r'(?m)^allowed-tools:\s*(.+)$', front)
    assert line and line[1].strip() == INVOCATION
    assert CALL in body
    named = set(re.findall(r'scripts/[\w./-]*[\w-]', body))
    assert not [n for n in sorted(named) if not (SKILL / n).exists()]
