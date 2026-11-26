"""素材的**归属**规矩：**事实入库，素材不入库**。

这一条是 aim 仓存在的理由之一：它生成「人」，而「人」带一堆东西——
立绘、姿态表、头像、品牌片底板、样例视频、品牌成品音轨。
那些东西的版权与口味是**用这套东西的人**自己的，仓库要发布给所有人，
所以**不入库**。入库的是**事实**：

| 入库的 | 为什么 |
| --- | --- |
| `models/<slug>/model.json` | 这个人的定义：音色、形象、人格、身份 |
| `models/<slug>/brand_windows.json` | 品牌片头尾的配乐窗口（挑窗的决策） |
| `assets/fonts/*.otf` | 字体子集是**框架**的一部分——两台机器用同一份字体文件，跨机版式才一致 |

不入库的是**素材**：媒体文件只写**路径**（在 `model.json` 里），
文件本身留在本机（`.gitignore` 挡住）。

**入库的只有事实**：模型契约与内置字体入库，素材不入库。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

AIM_ROOT = Path(__file__).resolve().parents[1]

#: 规则级素材：相对仓根的路径 → 为什么它跟着框架走
RULE_ASSETS = {
    "assets/fonts/AIVSansCJKSC-Regular.otf": "内置中文字体（跨机版式一致）",
    "assets/fonts/AIVSansCJKSC-Bold.otf": "内置中文字体的粗体面（cairo 会自己合成粗体）",
    "assets/fonts/AIVMonoCJKSC-Regular.otf": "内置等宽中文字体",
    "assets/fonts/SOURCE.json": "字体子集的来源记录（哪一份原字体的哪些字）",
}

#: 用户素材的**目录**：这些目录里不许有被跟踪的文件。
#:
#: 目录而不是具体文件——换素材的人自己决定文件名，规矩是文件不跟着仓库走。
USER_ASSET_DIRS = {
    "assets/character": "立绘与姿态表（形象素材：版权与口味是用这套东西的人自己的）",
    "assets/brand": "品牌片底板与品牌成品音轨（这一家的东西）",
    "assets/samples": "样例视频（不入库，由使用者自己保存）",
    "models/*/assets": "模型目录里的素材（路径写在 model.json 里，文件不入库）",
}

#: 事实文件：**必须**入库——它们记的是「这个人是谁」，不是素材。
FACT_FILES = {
    "models/growdu/model.json": "这个人的定义（音色、形象、人格、身份）",
    "models/growdu/brand_windows.json": "品牌片头尾的配乐窗口（挑窗决策）",
}

#: 媒体文件的后缀——「入库的媒体只有规则级那些」这条判据用它。
MEDIA_SUFFIXES = (".mp3", ".mp4", ".wav", ".png", ".jpg", ".jpeg", ".ttc")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=AIM_ROOT, capture_output=True, text=True
    )


@pytest.fixture(scope="module", autouse=True)
def _require_git_repo():
    if _git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("不在 git 仓库里，跳过")


@pytest.mark.parametrize("relative", sorted(RULE_ASSETS))
def test_rule_asset_is_tracked(relative):
    """规则级素材必须在版本控制里，否则别的机器上会凭空消失。"""
    assert (AIM_ROOT / relative).is_file(), f"{relative} 本机就没有"
    result = _git("ls-files", "--error-unmatch", relative)
    assert result.returncode == 0, (
        f"{relative} 没被 git 跟踪（{RULE_ASSETS[relative]}）——"
        f"别的机器 clone 完会缺这一件"
    )


@pytest.mark.parametrize("relative", sorted(FACT_FILES))
def test_fact_file_is_tracked(relative):
    """事实文件必须入库——不然别的机器上没有人知道「这个人是谁」。"""
    assert (AIM_ROOT / relative).is_file(), f"{relative} 本机就没有"
    result = _git("ls-files", "--error-unmatch", relative)
    assert result.returncode == 0, (
        f"{relative} 没被 git 跟踪（{FACT_FILES[relative]}）"
    )


@pytest.mark.parametrize("directory", sorted(USER_ASSET_DIRS))
def test_user_assets_are_not_tracked(directory):
    """用户自带的素材**不入库**——版权是他们的，仓库要发给所有人。"""
    result = _git("ls-files", directory)
    tracked = [
        line for line in result.stdout.splitlines()
        if line.strip() and not line.endswith((".py", ".sh", ".md", ".json", ".gitkeep"))
    ]
    assert tracked == [], (
        f"{directory} 里有被跟踪的用户素材：{tracked}"
        f"（{USER_ASSET_DIRS[directory]}）——把它从仓库里拿掉，"
        f"位置写进 model.json"
    )


def test_no_tracked_media_outside_the_rule_assets():
    """入库的媒体文件只有规则级那些（字体）。

    **字体是框架的一部分**（跨机版式一致）；立绘、曲子、品牌片是
    使用者自带的，一律不入库。
    """
    result = _git("ls-files")
    unexpected = [
        path for path in result.stdout.splitlines()
        if path.endswith(MEDIA_SUFFIXES) and path not in RULE_ASSETS
    ]
    assert unexpected == [], f"有媒体文件没走白名单就入库了：{unexpected}"
