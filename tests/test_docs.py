"""**文档里的链接不许断。**

**为什么这是条守卫**：教程是**给人看的**——
链接断在「相对路径基准错了」「文件挪了没改引用」这两种最常见的事上，
读者点不开就是**交付形式当场说不清**。
仓里已经有三份互相引用的文档（`README` / `AGENTS` / `specs/`）
加一份新写的教程，链接只会越来越多。

所以守一件事：**仓内文档里指向仓内的相对链接都得指得到东西。**

**只查相对链接**：外链（`https://`）本仓管不着，也不该在 CI 里联网去验。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from aimkit import paths

AIM_ROOT = paths.AIM_ROOT

#: 要查的文档：仓根那几份 + `docs/` 与 `specs/` 下的全部。
DOCS = sorted(
    [AIM_ROOT / "README.md", AIM_ROOT / "AGENTS.md"]
    + list((AIM_ROOT / "docs").glob("*.md"))
    + list((AIM_ROOT / "specs").glob("*.md"))
)

#: markdown 里的链接：`[文字](目标)`。
#: 只取相对目标——`http(s)://`、锚点（`#…`）、`mailto:` 都不是仓内路径。
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

#: `http` / `https` / `mailto` / 锚点 / 空。
NOT_A_PATH = ("http://", "https://", "mailto:", "#")


def _relative_links(doc: Path) -> list[str]:
    text = doc.read_text(encoding="utf-8")
    out = []
    for target in LINK.findall(text):
        target = target.strip()
        if not target or target.startswith(NOT_A_PATH):
            continue
        out.append(target)
    return out


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.relative_to(AIM_ROOT).as_posix())
def test_the_relative_links_point_at_something(doc: Path):
    broken = []
    for target in _relative_links(doc):
        # 链接里可能带锚点（`xxx.md#节`）——路径部分是锚点前头。
        path_part = target.split("#", 1)[0]
        if not path_part:
            continue
        resolved = (doc.parent / path_part).resolve()
        if not resolved.exists():
            broken.append(f"{target} → {resolved}")
    assert not broken, f"{doc.name} 里的链接指不到东西：{broken}"


def test_the_tutorial_is_there():
    """**教程不许悄悄没了**——它是「怎么用」的正片。"""
    tutorial = AIM_ROOT / "docs" / "使用教程.md"
    assert tutorial.is_file(), f"教程不在：{tutorial}"
    assert tutorial.stat().st_size > 2000, "教程短得不像样——是不是写空了"
