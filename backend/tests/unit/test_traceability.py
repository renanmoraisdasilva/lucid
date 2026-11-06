from pathlib import Path
import shutil
import subprocess

import pytest


def test_documentation_and_tests_move_together() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")

    repo = Path(__file__).resolve().parents[3]
    cli = repo / "node_modules" / "trace-docs" / "dist" / "cli" / "index.js"
    result = subprocess.run(
        [node, str(cli), "--root", str(repo), "verify"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
