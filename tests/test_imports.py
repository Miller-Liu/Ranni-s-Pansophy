"""Windows-only code must load lazily, so everything imports (and tests run) on any OS."""

import ast
import importlib
from pathlib import Path

SRC = Path(__file__).parent.parent / "src" / "ranni"
WINDOWS_PACKAGES = {"winrt", "dxcam", "mss"}


def _module_level_imports(path):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_windows_packages_load_lazily():
    for path in SRC.rglob("*.py"):
        if path == SRC / "ocr" / "windows.py":
            continue  # only ever imported on Windows
        for name in _module_level_imports(path):
            assert name.split(".")[0] not in WINDOWS_PACKAGES, f"{path} imports {name} at module level"
            assert name != "ranni.ocr.windows", f"{path} imports ranni.ocr.windows at module level"


def test_every_module_imports():
    for path in SRC.rglob("*.py"):
        if path == SRC / "ocr" / "windows.py":
            continue
        module = ".".join(path.relative_to(SRC.parent).with_suffix("").parts).removesuffix(".__init__")
        importlib.import_module(module)
