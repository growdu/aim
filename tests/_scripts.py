"""按路径载入脚本模块。

**为什么要这么麻烦**：aim 的脚本不是包——它们是**命令行脚本**，
彼此 `import` 同目录的模块（`generate_character.py` import `_mcode`）。
所以载入时要把**脚本所在目录**放进 `sys.path`。

**模块名要唯一**：同一个脚本被两个测试文件载入时会各存一份，
`sys.modules` 里撞名会让 dataclass 之类的回查拿到另一份模块。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

AIM_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = AIM_ROOT / "scripts"
SPECS_DIR = AIM_ROOT / "specs"


def load_script(relative: str, name: str | None = None):
    """载入 `scripts/<relative>`。

    `relative` 是相对 `scripts/` 的路径，例如 `character/add_glasses.py`。
    """
    path = SCRIPTS_DIR / relative
    if not path.is_file():
        raise FileNotFoundError(f"脚本不在：{path}")

    directory = str(path.parent)
    if directory not in sys.path:
        sys.path.insert(0, directory)

    module_name = name or f"aim_script_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    # **先注册进 sys.modules**：模块里的 dataclass 机制要回查
    # `sys.modules[cls.__module__]`。
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def spec_text(name: str) -> str:
    """读一份规范（`specs/<name>`）。"""
    return (SPECS_DIR / name).read_text(encoding="utf-8")
