"""人格的视觉体现——**唯一来源是 `model.json` 的 `persona`**。

人格是**一整段可读的文字**，不是关键词数组：生成 prompt 直接用它。
《人格规范》（`specs/人格规范.md` §一/§二）说清它该怎么写。

**为什么不是关键词数组**：关键词只能「挑」，不能「写」。
一段话能说清气质（冷静克制、工程师、秩序感……）之间的**关系**，
关键词列表做不到——同一个词在不同句子里意思不同。

规范改了 `model.json` 里的 `persona` 就要一起改（`tests/test_persona.py` 盯着）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aimkit import model as model_mod  # noqa: E402


def persona_prompt() -> str:
    """人格气质——直接进形象生成的 prompt。

    **可以是一整段，也可以是空的**：人格还没定，就先空着。
    """
    return model_mod.load().persona


def __getattr__(name: str) -> str:
    """`PERSONA_PROMPT` 惰性取（不在 import 时就要求模型存在）。"""
    if name == "PERSONA_PROMPT":
        return persona_prompt()
    raise AttributeError(name)
