"""形象这一侧：**眼镜规格 ↔ 规范 ↔ prompt**，素材位置跟着模型走。

眼镜为什么单独立一条守卫：镜框色写死在 `add_glasses.py` 的常量里，
规范与生成 prompt 必须写的是同一件事——两边漂了，下一次重生成就会
得到一只没戴眼镜、或戴错颜色的形象，而**画面照样生成、时长照样对**，
没有任何报错。

素材位置同理：`model.json` 声明的路径与脚本实际写出的路径必须一致，
否则模型换人之后，下游找不到的那张图就在别处。
"""
from __future__ import annotations

from pathlib import Path

from aimkit import model as model_mod
from aimkit import paths as aim_paths

from _scripts import load_script, spec_text

_MODEL = model_mod.load()


def _add_glasses():
    return load_script("character/add_glasses.py", "aim_script_add_glasses")


def _generate_character():
    return load_script("character/generate_character.py",
                        "aim_script_generate_character")


def test_the_glasses_colour_comes_from_the_model():
    """镜框色与款式 = **模型里的**那一份。

    规格以前写死在脚本里（`GLASSES_COLOR = "#2B4C7E"`）——换人就换不掉，
    生成出来的还是上一个人的样子，而画面照样生成、时长照样对。

    规范里的镜框色（**这个人的例子**）也要跟模型一致：
    规范与模型漂了，下次重生成就会戴错颜色。
    """
    glasses = _add_glasses()
    spec = spec_text("形象规范.md")
    declared = (_MODEL.look_spec.get("glasses") or {})

    assert glasses.GLASSES_COLOR == declared.get("color")
    assert glasses.GLASSES_STYLE == declared.get("style")
    assert glasses.GLASSES_COLOR in spec, (
        f"规范里没有镜框色 {glasses.GLASSES_COLOR}——"
        "规范与模型漂了，下次重生成就会戴错颜色"
    )
    assert glasses.GLASSES_STYLE in spec, (
        f"规范里没有镜框样式「{glasses.GLASSES_STYLE}」"
    )


def test_the_glasses_prompt_carries_the_spec():
    """生成 prompt 里必须写着那副眼镜——写漏了就是「没戴眼镜」。"""
    glasses = _add_glasses()
    prompt = glasses.build_prompt()

    assert glasses.GLASSES_COLOR in prompt
    assert glasses.GLASSES_STYLE in prompt
    assert "透明" in prompt, "镜片透明是硬要求（镜片一反光，眼睛就废了）"


def test_the_cleanup_prompt_targets_the_glasses_nameplate():
    """擦镜框杂物的 prompt 得说清楚擦什么。"""
    glasses = _add_glasses()
    assert "白色小铭牌" in glasses.CLEANUP_PROMPT
    assert "白色小铭牌" in glasses.CLEANUP_SHEET_PROMPT


def test_the_character_output_lands_in_the_person_asset_dir():
    """脚本写出的目录 = 这个人的素材目录（`models/<slug>/assets/character/`）。"""
    glasses = _add_glasses()

    assert glasses.PERSON_ROOT == aim_paths.person_assets_dir(_MODEL.person)
    assert glasses.PERSON_ROOT == _MODEL.base / "assets"
    assert glasses.STAGING == aim_paths.model_dir(_MODEL.person) / "_staging"


def test_the_batch_targets_live_under_the_person_asset_dir():
    """批次里的相对路径都落在 `models/<slug>/assets/` 底下。"""
    glasses = _add_glasses()
    for relative, _transparent, _ratio in glasses.BATCH:
        assert not Path(relative).is_absolute(), relative
        assert relative.startswith(("character/", "brand/")), relative
        assert (glasses.PERSON_ROOT / relative).is_relative_to(
            glasses.PERSON_ROOT)


def test_the_main_image_the_model_declares_is_the_one_we_produce():
    """模型声明的透明底主形象 = 脚本产出的那一张。

    **这条是给下游用的**：下游只认 `model.json` 里 `assets.mascot`
    指到的那张图。两边名字对不上，下游就找不到素材——而画面照样
    生成、时长照样对，只在合成角色时缺一块。
    """
    glasses = _add_glasses()
    clear = load_script("character/clear_badge.py", "aim_script_clear_badge")

    derived = glasses.PERSON_ROOT / glasses.DERIVED[0]
    assert derived == _MODEL.asset("mascot"), (
        f"模型说主形象在 {_MODEL.asset('mascot')}，"
        f"脚本写出的却是 {derived}"
    )

    plain = glasses.PERSON_ROOT / "character" / clear.OUTPUT_NAME
    assert plain == _MODEL.asset("mascot_plain"), (
        f"模型说无标牌版在 {_MODEL.asset('mascot_plain')}，"
        f"脚本写出的却是 {plain}"
    )


def test_the_source_image_is_the_one_the_model_declares():
    """形象原型参考图 = 模型里声明的那张。"""
    generator = _generate_character()
    assert generator.SOURCE_IMAGE == _MODEL.asset("source")


def test_the_look_description_reaches_the_prompt():
    """外观描述取自模型的 `look`，并进了 prompt。"""
    generator = _generate_character()
    assert generator.LOOK == _MODEL.look
    assert _MODEL.look and _MODEL.look in generator.CHARACTER_PROMPT
    assert _MODEL.look in generator.POSE_PROMPT


def test_the_character_prompt_carries_the_glasses_spec():
    """主形象 prompt 里也有那副眼镜。"""
    generator = _generate_character()
    assert generator.GLASSES_COLOR in generator.CHARACTER_PROMPT
    assert generator.GLASSES_COLOR in generator.POSE_PROMPT


def test_the_brand_token_reaches_the_badge():
    """铭牌上的字 = 模型的 `brand.token`（空着不行）。"""
    generator = _generate_character()
    assert generator.BRAND_NAME == _MODEL.brand.get("name", "")
    assert _MODEL.brand.get("token"), "铭牌必须有品牌词"
