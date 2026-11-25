"""人格：**一整段可读的文字**，唯一来源是 `model.json` 的 `persona`。

**为什么人格不是关键词数组**：关键词只能「挑」，不能「写」。
一段话能说清气质之间的**关系**（冷静克制、工程师、秩序感……），
同一个词在不同句子里意思不同——列表做不到。

**为什么要有守卫**：`persona` 同时喂给**规范**与**形象生成的 prompt**。
两边漂了，画面上长出来的气质就跟写下来的人格对不上，
而**画面照样生成、时长照样对**，没有任何报错。
"""
from __future__ import annotations

from aimkit import model as model_mod

from _scripts import load_script, spec_text

_MODEL = model_mod.load()

#: 《人格规范》§1.1 定的五条视觉气质。**规则**，不是这个人特有的。
TRAITS = ("冷静克制", "工程师", "秩序感", "专注", "可靠")


def _persona_module():
    return load_script("character/_persona.py", "aim_script_persona")


def test_the_persona_is_a_paragraph():
    """人格是**一整段文字**，不是列表。"""
    persona = _MODEL.persona
    assert isinstance(persona, str), f"人格是 {type(persona).__name__}，不是文字"
    assert len(persona) >= 40, "人格太短——一段话才说得清气质之间的关系"
    assert "\n" in persona, "人格要分行写：一条气质一行"


def test_the_persona_is_not_a_keyword_list():
    """原始 JSON 里也不能是数组——那是旧的做法。"""
    raw = _MODEL.raw.get("persona")
    assert isinstance(raw, str), "model.json 的 persona 必须是一段文字"
    assert not raw.strip().startswith("["), "人格不是关键词数组"


def test_the_keyword_list_is_retired():
    """`PERSONA_TRAITS` 已经退休——它就是这个仓要消灭的东西。"""
    module = _persona_module()
    assert not hasattr(module, "PERSONA_TRAITS")
    assert hasattr(module, "PERSONA_PROMPT"), (
        "PEP-562 的 `__getattr__` 还得能惰性给出 PERSONA_PROMPT"
    )


def test_the_persona_comes_from_the_model():
    """人格的**唯一来源**是 `model.json`。"""
    module = _persona_module()
    assert module.persona_prompt() == _MODEL.persona
    assert module.PERSONA_PROMPT == _MODEL.persona


def test_the_five_traits_of_the_spec_are_in_the_persona():
    """《人格规范》§1.1 的五条气质，模型里一条都不能少。"""
    persona = _MODEL.persona
    missing = [trait for trait in TRAITS if trait not in persona]
    assert not missing, (
        f"人格里少了 {missing}——规范 §1.1 定的五条气质，"
        "改模型就要一起改规范"
    )


def test_the_spec_lists_the_same_five_traits():
    """规范里的那五条 = 守卫盯着的那五条。"""
    spec = spec_text("人格规范.md")
    missing = [trait for trait in TRAITS if trait not in spec]
    assert not missing, f"《人格规范》里少了 {missing}——守卫要跟着改"


def test_the_persona_reaches_the_character_prompt():
    """人格进形象生成的 prompt——不然画面上只有长相、没有气质。"""
    generator = load_script("character/generate_character.py",
                            "aim_script_generate_character")
    assert _MODEL.persona in generator.CHARACTER_PROMPT
    assert _MODEL.persona in generator.POSE_PROMPT
