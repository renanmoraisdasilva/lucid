# pyright: basic
"""Enforce the code health budget defined in docs/plans/code-health-budget.md.

This is intentionally a test rather than a separate script: it runs in the normal
suite and cannot be skipped without a visible failure. Thresholds mirror the
document; change both together.
"""

import ast
from pathlib import Path

from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.visitors import Function

BACKEND = Path(__file__).resolve().parents[1]
SOURCE_ROOT = BACKEND / "src" / "lucid"
TEST_ROOT = BACKEND / "tests"

SOURCE_FILE_MAX = 300
PROVIDER_FILE_MAX = 350
TEST_FILE_MAX = 600
FUNCTION_MAX = 50
TEST_FUNCTION_MAX = 80
PARAMS_MAX = 5
NESTING_MAX = 4
CC_MAX = 12
MI_MIN = 30

# Declarative or wiring modules whose length is not a design signal.
FILE_EXEMPT = {
    "config.py",
    "persistence/tables.py",
}
CONTROL_FLOW = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match)


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts and ".venv" not in path.parts
    )


def _max_nesting(node: ast.AST, depth: int = 0) -> int:
    deepest = depth
    for child in ast.iter_child_nodes(node):
        next_depth = depth + 1 if isinstance(child, CONTROL_FLOW) else depth
        deepest = max(deepest, _max_nesting(child, next_depth))
    return deepest


def _function_violations(
    path: Path, tree: ast.AST, limit: int, *, check_params: bool = True
) -> list[str]:
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        args = node.args.posonlyargs + node.args.args
        params = len([arg for arg in args if arg.arg not in {"self", "cls"}])
        params += len(node.args.kwonlyargs)
        if length > limit:
            problems.append(f"{path}:{node.lineno}: function {node.name} is {length} lines")
        if check_params and params > PARAMS_MAX:
            problems.append(f"{path}:{node.lineno}: function {node.name} has {params} parameters")
        nesting = _max_nesting(node)
        if nesting > NESTING_MAX:
            problems.append(f"{path}:{node.lineno}: function {node.name} nests {nesting} levels")
    return problems


def _complexity_violations(path: Path, source: str) -> list[str]:
    problems: list[str] = []
    for block in cc_visit(source):
        if not isinstance(block, Function):
            continue
        if block.complexity > CC_MAX:
            problems.append(
                f"{path}:{block.lineno}: function {block.name} has CC {block.complexity}"
            )
    return problems


def _source_violations() -> list[str]:
    problems: list[str] = []
    for path in _python_files(SOURCE_ROOT):
        relative = path.relative_to(SOURCE_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        file_limit = PROVIDER_FILE_MAX if relative.startswith("providers/") else SOURCE_FILE_MAX
        lines = len(source.splitlines())
        if relative not in FILE_EXEMPT and lines > file_limit:
            problems.append(f"{path}: {lines} lines (limit {file_limit})")
        problems.extend(_function_violations(path, tree, FUNCTION_MAX))
        problems.extend(_complexity_violations(path, source))
        if relative not in FILE_EXEMPT:
            score = mi_visit(source, multi=True)
            if score < MI_MIN:
                problems.append(f"{path}: maintainability index {score:.2f} (min {MI_MIN})")
    return problems


def _test_violations() -> list[str]:
    problems: list[str] = []
    for path in _python_files(TEST_ROOT):
        relative = path.relative_to(TEST_ROOT).as_posix()
        if relative in {"__init__.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        if len(source.splitlines()) > TEST_FILE_MAX:
            problems.append(f"{path}: {len(source.splitlines())} lines (limit {TEST_FILE_MAX})")
        problems.extend(_function_violations(path, tree, TEST_FUNCTION_MAX, check_params=False))
    return problems


def test_code_health_budget() -> None:
    problems = _source_violations() + _test_violations()
    assert not problems, "Code health budget exceeded:\n" + "\n".join(problems)
