"""守卫：代码里不许写死任何一个**具体的人**。

**为什么要有这条。** 「换人只改模型，不改代码」是本仓的规矩，
但规矩靠自觉是会漏的：脚本里写死一句配色、一个品牌名、一个定位，
换个人之后**画面照样生成、时长照样对**，没有任何报错——
只是生成出来的是**上一个人的样子**。这种错最难查：它不崩。

所以这条守卫**从模型反推**：把当前这个人的专属字符串
（标识、品牌名、配色、定位、人设…）全列出来，扫一遍代码——
代码里出现任何一个，就是写死了这个人。

**为什么扫的是「这个人的事实」而不是一份写死的名单**：
名单会过期（换人就失效），而且只能挡住当初想到的那几条。
从模型反推，换了人，守卫自动跟着换。

**为什么只扫代码，不扫 `specs/`**：规范里的**例子**本来就是这个人的
（规则是框架的，例子是这个人的）。规范与模型对不上，由形象那条守卫管。
"""
from __future__ import annotations

import re
from pathlib import Path

from aimkit import look
from aimkit import model as model_mod
from aimkit import paths

AIM_ROOT = paths.AIM_ROOT
MODEL = model_mod.load()

#: 要扫的目录：**代码**。规范与素材不在其中。
CODE_DIRS = (AIM_ROOT / "aimkit", AIM_ROOT / "scripts")

#: 太短的字符串不查——「像」「深」这种词出现在代码里是正常的，
#: 拿它们当「写死了这个人」是误报。
MIN_FACT_LENGTH = 4


def _person_facts() -> list[str]:
    """**这个人的**专属字符串——从模型里挖出来。"""
    facts: list[str] = []

    def add(value: object) -> None:
        if isinstance(value, str) and len(value.strip()) >= MIN_FACT_LENGTH:
            facts.append(value.strip())

    add(MODEL.person)
    add(MODEL.look)
    for key in ("name", "token", "site", "tagline", "intro_tagline",
                "intro_line", "outro_line", "outro_narration",
                "outro_subtitle", "outro_title", "share_suffix",
                "share_emphasis"):
        add(MODEL.brand.get(key))
    for key in ("name", "role", "positioning", "audience", "series"):
        add(MODEL.identity.get(key))
    for taboo in MODEL.identity.get("taboos") or []:
        add(taboo)

    spec = MODEL.look_spec
    glasses = spec.get("glasses")
    if isinstance(glasses, dict):
        add(glasses.get("style"))
        add(glasses.get("color"))
    for key in ("vest_color", "badge_icon_color", "badge_text_color",
                "headset"):
        add(spec.get(key))
    for which in ("deep", "light"):
        add(MODEL.brand_colour(which))
    return facts


def _code_files() -> list[Path]:
    files: list[Path] = []
    for directory in CODE_DIRS:
        if not directory.is_dir():
            continue
        files.extend(sorted(directory.rglob("*.py")))
    return files


def test_the_code_does_not_hardcode_this_person():
    """代码里不许出现这个人的专属字符串。"""
    facts = _person_facts()
    assert facts, "模型里一个专属字符串都没挖到——守卫可能是瞎的"

    offenders: list[str] = []
    for path in _code_files():
        text = path.read_text(encoding="utf-8")
        for fact in facts:
            if fact in text:
                offenders.append(f"{path.relative_to(AIM_ROOT)}：{fact!r}")

    assert offenders == [], (
        "代码里写死了这个人的事实：\n  "
        + "\n  ".join(offenders)
        + "\n换人只改模型，不改代码——这些得挪进 model.json。"
    )


def _wanted_colours() -> list[str]:
    """这个人的配色——形象上的与品牌片底板上的。"""
    spec = MODEL.look_spec
    colours = [
        spec.get("vest_color"),
        spec.get("badge_icon_color"),
        spec.get("badge_text_color"),
    ]
    glasses = spec.get("glasses")
    if isinstance(glasses, dict):
        colours.append(glasses.get("color"))
    colours.extend(MODEL.brand_colour(which) for which in ("deep", "light"))
    # 去重但保序——同一个颜色被声明两遍（马甲与底板同色）只报一次。
    unique: list[str] = []
    for colour in colours:
        if isinstance(colour, str) and colour.strip() and colour not in unique:
            unique.append(colour)
    return unique


def _variants(colour: str) -> list[str]:
    """一个颜色在代码里可能写成的**几种样子**。

    只查 `#RRGGBB` 是不够的——写死配色的人更常写成
    `(43 / 255, 76 / 255, 126 / 255)` 这样的三元组，
    **看源码扫颜色扫不出来**，这正是它藏得住的原因。
    """
    rgb = look.hex_to_rgb(colour)
    if rgb is None:
        return [colour]
    r, g, b = rgb
    return [
        colour,
        f"{r}, {g}, {b}",
        f"{r} / 255, {g} / 255, {b} / 255",
        f"{r / 255:.3f}, {g / 255:.3f}, {b / 255:.3f}",
    ]


def _squash(text: str) -> str:
    """去掉全部空白——免得 `43 / 255` 与 `43/255` 两种写法各算一种。"""
    return re.sub(r"\s+", "", text)


def test_the_code_does_not_hardcode_the_colours():
    """配色是最容易漏的一类——它不像名字，一眼扫不出来。

    这条单独拎出来：配色写死了，画面照样生成、时长照样对，
    只是那个人换了一身衣服。

    **查的不只是 `#RRGGBB`**：三元组写法（`43 / 255, 76 / 255, 126 / 255`）
    一样是写死这个人的配色，一样得挪进模型。
    """
    wanted = _wanted_colours()
    assert wanted, "模型里一个配色都没挖到——守卫可能是瞎的"

    offenders: list[str] = []
    for path in _code_files():
        text = _squash(path.read_text(encoding="utf-8"))
        for colour in wanted:
            for variant in _variants(colour):
                if _squash(variant) in text:
                    offenders.append(
                        f"{path.relative_to(AIM_ROOT)}：{colour}"
                        f"（写成 {variant}）"
                    )
                    break

    assert offenders == [], (
        "代码里写死了这个人的配色：\n  "
        + "\n  ".join(offenders)
        + "\n配色是模型的事（`look_spec` / `brand.colors`），代码只管读。"
    )
