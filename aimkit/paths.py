"""aim 仓里各处路径的**唯一出处**。

谁想拼路径，从这里拿；别在脚本里手写 `parents[2]` 之类。

**布局的一句话说清**：一个人的东西都在 `aim/models/<slug>/` 底下——
`model.json`（他是谁）、`brand_windows.json`（配乐窗口）、
`assets/`（他的立绘与品牌片素材，**不入库**）。
字体子集是仓级的，在 `aim/assets/fonts/`（**入库**）。
"""
from __future__ import annotations

from pathlib import Path

#: 仓根（`aim/`）。
AIM_ROOT = Path(__file__).resolve().parents[1]

#: 每个人的模型目录的父目录（`aim/models/`）。
MODELS_DIR = AIM_ROOT / "models"

#: 仓级素材（`aim/assets/`）——现在只有**入库的字体子集**。
ASSETS_DIR = AIM_ROOT / "assets"

#: 字体子集（`aim/assets/fonts/`）——**入库**，跨机版式靠它。
FONTS_DIR = ASSETS_DIR / "fonts"

#: 规范文档（`aim/specs/`）。
SPECS_DIR = AIM_ROOT / "specs"

#: 脚本（`aim/scripts/`）。
SCRIPTS_DIR = AIM_ROOT / "scripts"

#: 测试（`aim/tests/`）。
TESTS_DIR = AIM_ROOT / "tests"


def model_dir(slug: str) -> Path:
    """某个人的模型目录（`aim/models/<slug>/`）。"""
    return MODELS_DIR / slug


def model_path(slug: str) -> Path:
    """某个人的 `model.json`（`aim/models/<slug>/model.json`）。"""
    return model_dir(slug) / "model.json"


def person_assets_dir(slug: str) -> Path:
    """某个人的素材目录（`aim/models/<slug>/assets/`）——**不入库**。"""
    return model_dir(slug) / "assets"


def character_dir(slug: str) -> Path:
    """某个人的立绘、姿态表、头像（**不入库**）。"""
    return person_assets_dir(slug) / "character"


def brand_dir(slug: str) -> Path:
    """某个人的品牌片底板与音频（**不入库**）。"""
    return person_assets_dir(slug) / "brand"


def samples_dir(slug: str) -> Path:
    """某个人的样例视频（**不入库**，由使用者自己保存）。"""
    return person_assets_dir(slug) / "samples"
