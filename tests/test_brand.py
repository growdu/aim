"""品牌片这一侧：**字体有出处**、**画出去的字不缺**、**文案取自模型**。

品牌片是**独立于渲染流水线的一条出字路**——它自己用 cairo 画字。
漏了它的后果是品牌片上出现豆腐块，而**画面照常生成、时长照常对**，
没有任何报错，只有盯着字才看得见。

所以这里有两类守卫：

1. **字体的出处**：内置字体子集是按 GB 2312-80 全集子集化的静态拷贝，
   台账钉住上游 URL、版本与 sha256。字库换了没人知道，是最坏的一种坏。
2. **真正画出去的字**：把片头 / 片尾真渲一遍，收齐画上去的每一个字，
   核对字体里有没有。**不看源码，看画面**——源码改不动它。

另一半（场景与字幕的出字路）不在本仓——那边才是画场景与烧字幕的地方。
本仓的字体子集**入库**，跨机靠同一份文件（sha256 钉住）。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from aimkit import fonts
from aimkit import model as model_mod
from aimkit import paths as aim_paths

from _scripts import load_script

_MODEL = model_mod.load()

FONT_DIR = aim_paths.FONTS_DIR
MANIFEST = FONT_DIR / "SOURCE.json"

#: 内置字体的两面。**两个字重都要有**——只装常规字重的话，cairo 会
#: **合成**粗体，而合成是各后端自己的做法，两个平台合成出来的不一样。
SUBSETS = {
    "Regular": FONT_DIR / "AIVSansCJKSC-Regular.otf",
    "Bold": FONT_DIR / "AIVSansCJKSC-Bold.otf",
}

#: **等宽**那一族（代码块用）。
MONO_SUBSET = FONT_DIR / "AIVMonoCJKSC-Regular.otf"

#: **GB 2312-80**：两字节编码，首字节与次字节都是 0xA1–0xFE。
#: 逐个解码就是汉字区与符号区的全集——**不依赖任何外部数据**。
GB2312_LEAD = 0xA1
GB2312_TRAIL = 0xA1
GB2312_LEAD_MAX = 0xFE
GB2312_TRAIL_MAX = 0xFE

#: 运行时探针采样几个时刻——一段动画的中间态才有话说。
PROBE_TIMES = (0.0, 0.25, 0.5, 0.75, 1.0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _cmap(path: Path) -> dict:
    from fontTools.ttLib import TTFont

    return TTFont(str(path)).getBestCmap()


def _gb2312_chars() -> set[str]:
    chars: set[str] = set()
    for lead in range(GB2312_LEAD, GB2312_LEAD_MAX + 1):
        for trail in range(GB2312_TRAIL, GB2312_TRAIL_MAX + 1):
            try:
                chars.add(bytes((lead, trail)).decode("gb2312"))
            except UnicodeDecodeError:
                continue
    return chars


def _render_brand():
    return load_script("brand/render_brand.py", "aim_script_render_brand")


# ---------------------------------------------------------------- 字体出处


def test_the_bundled_font_is_present():
    for style, path in SUBSETS.items():
        assert path.is_file(), f"内置字体（{style}）不在：{path}"
    assert MONO_SUBSET.is_file(), f"内置等宽字体不在：{MONO_SUBSET}"
    assert MANIFEST.is_file(), f"字体出处台账不在：{MANIFEST}"


def test_the_manifest_pins_the_upstream_source():
    """出处台账必须钉住版本与 sha256——不然换一份字体没人知道。"""
    data = _manifest()
    assert data["family"] == fonts.BUNDLED_FAMILY
    assert data["mono_family"] == fonts.BUNDLED_MONO_FAMILY
    assert data["license"] == "SIL Open Font License 1.1"
    assert data["version"]

    faces = data["faces"]
    assert [(face["family"], face["style"]) for face in faces] == [
        ("AIV Sans CJK SC", "Regular"),
        ("AIV Sans CJK SC", "Bold"),
        ("AIV Mono CJK SC", "Regular"),
    ], faces
    for face in faces:
        assert face["upstream"].startswith("https://"), face
        assert re.fullmatch(r"[0-9a-f]{64}", face["subset_sha256"]), face
        assert face["subset_bytes"] > 0, face
        if face["source"] == "upstream":
            assert re.fullmatch(r"[0-9a-f]{64}", face["upstream_sha256"]), face
        else:
            assert face["source"] == "offline_source", face
            assert face["source_postscript_name"], face
            assert face["source_ttc"], face


def test_the_manifest_records_the_offline_source():
    """台账里要钉住**离线源**——上游 CDN 连不上的机器靠它重建。"""
    offline = _manifest()["offline_source"]
    assert re.fullmatch(r"[0-9a-f]{64}", offline["sha256"]), offline
    assert offline["url"].startswith("https://"), offline
    assert offline["version_string"].startswith("Version "), offline
    assert set(offline["ttc"]) == {"Regular", "Bold"}, offline


def test_the_subset_file_matches_the_recorded_hash():
    """子集文件的 sha256 必须与台账一致——手改台账改不动文件。"""
    for face in _manifest()["faces"]:
        path = FONT_DIR / face["file"]
        assert path.is_file(), f"台账里记的文件不在：{path}"
        assert _sha256(path) == face["subset_sha256"], (
            f"子集文件 {face['file']} 与台账对不上——"
            f"重跑 scripts/build_font_subset.py"
        )


def test_both_weights_are_really_different_faces():
    """两个字重必须是**两份不同的真字形**，不能是同一份。

    判据用**轮廓包围盒**：合成粗体是在常规字形上「加粗」，
    包围盒会变，但步进不变——所以这里比轮廓，不比步进。
    """
    cairo = pytest.importorskip("cairo")

    extents = {}
    for style in ("Regular", "Bold"):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 100)
        ctx = cairo.Context(surface)
        fonts.select_font(
            ctx, fonts.BUNDLED_FAMILY, bold=(style == "Bold"))
        ctx.set_font_size(44)
        ctx.new_path()
        ctx.move_to(0, 60)
        ctx.text_path("A")
        extents[style] = ctx.path_extents()
        ctx.new_path()
    assert extents["Regular"] != extents["Bold"], (
        "两个字重的轮廓一模一样——粗体没装上，cairo 只能合成"
    )


def test_the_subset_covers_the_whole_gb2312_standard():
    """**内置字体必须盖住 GB 2312-80 全集**。

    **为什么要按标准算**：母稿不在这个仓里。照「仓里用到的字」算，
    母稿画出来一半是豆腐块，而画面照样生成、时长照样对。
    """
    standard = _gb2312_chars()
    assert len(standard) > 7000, (
        f"GB 2312-80 全集只有 {len(standard)} 个字——枚举口径不对")

    for style, path in SUBSETS.items():
        cmap = _cmap(path)
        missing = sorted(ch for ch in standard if ord(ch) not in cmap)
        assert not missing, (
            f"内置字体（{style}）缺 GB 2312-80 里的 {len(missing)} 个字："
            f"{missing[:20]}"
        )

    mono = _cmap(MONO_SUBSET)
    missing = sorted(ch for ch in standard if ord(ch) not in mono)
    assert not missing, (
        f"内置等宽字体缺 GB 2312-80 里的 {len(missing)} 个字：{missing[:20]}"
    )


def test_the_subset_is_small():
    """子集的意义在于小。超了说明提取范围写宽了。"""
    for style, path in SUBSETS.items():
        size = path.stat().st_size
        assert size < 5 * 1024 * 1024, f"子集（{style}）{size} 字节，太大了"
    size = MONO_SUBSET.stat().st_size
    assert size < 5 * 1024 * 1024, f"等宽子集 {size} 字节，太大了"


def test_the_bundled_family_name_is_unique():
    """内置族名不能跟系统里任何字体重名。

    重名了 fontconfig 就在两份之间二选一，机器之间就不一致了。

    **为什么用 `AIV ` 前缀**：系统里的中文字族名一个都不带这个前缀，
    所以重名不可能发生——这是命名约定带来的保证，不是运气。
    """
    assert fonts.BUNDLED_FAMILY == "AIV Sans CJK SC"
    assert fonts.BUNDLED_MONO_FAMILY == "AIV Mono CJK SC"
    assert fonts.BUNDLED_FAMILY.startswith("AIV ")
    assert fonts.BUNDLED_MONO_FAMILY.startswith("AIV ")

    # 兜底族名里除了**内置那两面**，不许再出现内置族名——
    # 出现就等于「它跟系统字体重名」。
    system_families = set(fonts.FALLBACK_FAMILIES) - {
        fonts.BUNDLED_FAMILY, fonts.BUNDLED_MONO_FAMILY}
    assert fonts.BUNDLED_FAMILY not in system_families
    assert fonts.BUNDLED_FAMILY not in {
        "PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC",
        "Heiti SC", "SimHei", "Microsoft YaHei", "sans-serif",
    }


# ---------------------------------------------------------------- 文案取自模型


def test_the_brand_text_comes_from_the_model():
    """品牌片上的文案**一律从模型读**，脚本里不写死。

    换一个人只改 `model.json`，不改代码。
    """
    brand = _render_brand()
    section = _MODEL.brand

    assert brand.BRAND_NAME == section.get("name", "")
    assert brand.BRAND_TOKEN == section.get("token", "")
    assert brand.BRAND_SITE == section.get("site", "")
    assert brand.INTRO_TAGLINE == section.get("intro_tagline", "")
    assert brand.OUTRO_TITLE == section.get("outro_title", "")
    assert brand.OUTRO_SUBTITLE == section.get("outro_subtitle", "")
    assert brand.OUTRO_LABELS == section.get("outro_labels", [])
    assert brand.OUTRO_NARRATION == section.get("outro_narration", "")


def test_the_plate_colours_come_from_the_model():
    """底板的两个颜色**从模型读**。

    它们以前是渲染脚本里的两行常量——换个人，片子还带着上一个人的配色，
    而画面照常生成、时长照常对。
    """
    from aimkit import look as look_spec

    brand = _render_brand()
    deep = _MODEL.brand_colour("deep")
    light = _MODEL.brand_colour("light")
    assert deep and light, "模型没声明底板配色"

    assert brand.DEEP == pytest.approx(look_spec.cairo_rgb(deep, (0.0, 0.0, 0.0)))
    assert brand.LIGHT == pytest.approx(look_spec.cairo_rgb(light, (1.0, 1.0, 1.0)))


def test_the_brand_token_is_present():
    """铭牌上的品牌词不能空——空着就没有品牌标识。"""
    assert _MODEL.brand.get("token", "").strip()


def test_the_declared_clips_live_under_the_brand_dir():
    """模型声明的品牌片与音轨 = 脚本写出的位置。

    下游只认 `model.json` 里 `brand.clips` / `brand.audio` 指到的文件，
    两边对不上，下游就拼不进去。
    """
    brand_dir = aim_paths.brand_dir(_MODEL.person)
    for kind in ("intro", "outro"):
        clip = _MODEL.brand_file("clips", kind)
        assert clip is not None, f"模型没声明 brand.clips.{kind}"
        assert clip.is_relative_to(brand_dir), f"{clip} 不在品牌目录底下"
        assert clip.suffix == ".mp4", clip

        audio = _MODEL.brand_file("audio", kind)
        assert audio is not None, f"模型没声明 brand.audio.{kind}"
        assert audio.is_relative_to(brand_dir), f"{audio} 不在品牌目录底下"


def test_the_brand_windows_file_is_declared():
    """配乐窗口决策跟着这个人走。"""
    windows = _MODEL.brand_file("windows")
    assert windows is not None
    assert windows.name == _MODEL.brand.get("windows", "")
    assert windows.is_relative_to(_MODEL.base)


# ---------------------------------------------------------------- 缺字守卫


def _drawn_chars() -> set[str]:
    """把**真正画出去**的字收齐（片头 + 片尾）。

    **不看源码，看画面**：把 `text()` 换成收集器，真渲一遍，
    收齐画上去的每一个字。
    """
    cairo = pytest.importorskip("cairo")
    from PIL import Image

    brand = _render_brand()
    seen: set[str] = set()

    def recorder(ctx, s, x, y, size, color, anchor="left", bold=False,
                 alpha=1.0):
        seen.update(s)
        return None

    original = brand.text
    brand.text = recorder
    try:
        bg = Image.new("RGB", (640, 360), (30, 40, 60))
        char = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 400)
        ctx = cairo.Context(char)
        ctx.set_source_rgba(1, 1, 1, 1)
        ctx.rectangle(0, 0, 200, 400)
        ctx.fill()

        for t in PROBE_TIMES:
            brand.render_intro_frame(t, bg, char, 0.9)
            brand.render_outro_frame(t, bg, char, 0.9)
    finally:
        brand.text = original

    return seen


def test_the_brand_render_actually_draws_text():
    """探针本身要真的画到字——不然它是个永远绿的空守卫。"""
    drawn = _drawn_chars()
    assert drawn, "片头片尾一个字都没画出来——探针瞎了"
    assert any("一" <= ch <= "鿿" for ch in drawn), "探针没收着汉字"


def test_the_brand_render_draws_only_characters_the_font_has():
    """**缺字就红**：品牌片画出去的每一个字，字体里都得有。

    这条守的是**运行时**：静态提取靠的是「画字模块列表」，
    而真正画字的路径可能绕开它。
    """
    drawn = _drawn_chars()
    missing = fonts.missing_chars("".join(sorted(drawn)))
    assert not missing, (
        f"品牌片画了字体里没有的字：{missing}——画面上就是豆腐块，"
        f"而时长照常对，没有任何报错"
    )
