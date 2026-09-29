import ast
from pathlib import Path

import stem_crop_tool.core


def test_core_does_not_import_pyside6() -> None:
    core_directory = Path(stem_crop_tool.core.__file__).parent
    violations: list[str] = []

    for source_path in core_directory.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "PySide6" or name.startswith("PySide6.") for name in names):
                violations.append(
                    f"{source_path.relative_to(core_directory)}:{node.lineno}"
                )

    assert violations == []
