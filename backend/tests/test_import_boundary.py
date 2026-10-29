"""The provider boundary is enforced, not just documented."""

import ast
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "lucid"
ALLOWED = {"lucid/providers/gemini.py"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_google_genai_is_only_imported_by_the_adapter() -> None:
    violations: list[str] = []

    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(SOURCE_ROOT.parent.parent).as_posix()
        relative = relative.removeprefix("src/")
        if relative in ALLOWED:
            continue
        for module in _imports(path):
            if module == "google.genai" or module.startswith("google.genai."):
                violations.append(f"{relative} imports {module}")

    assert violations == []


def test_application_layer_does_not_import_providers() -> None:
    violations: list[str] = []

    for path in sorted((SOURCE_ROOT / "application").rglob("*.py")):
        for module in _imports(path):
            if module.startswith("lucid.providers"):
                violations.append(f"{path.name} imports {module}")

    assert violations == []
