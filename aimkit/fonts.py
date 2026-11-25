"""字体解析——**精简版**。

aiv 的 `pyv/fonts.py` 有 700 行（它要给整条渲染链做跨机版式对齐）。
aim 只需要四件事：

1. 定下**哪个字体族名**；
2. 把 ctx 的字体设好（并且**关掉 hinting**）；
3. 判断**某个字画不画得出来**；
4. 画不出来就**报错**，不画豆腐块。

**跨仓零 import**：这里不 import aiv 的任何东西。
字体子集是**静态拷贝**（`assets/fonts/`），两边**同一份文件**——
aiv 侧有一条测试用 sha256 钉住（见 aiv 的 `tests/test_model_seam.py`）。

**为什么关 hinting**：hinting 会让「几何」不再是字体文件的性质。
cairo 在 Linux 上走 FreeType，默认开着 autohinter：轮廓点被吸附到像素网格，
度量被取整。于是「步进宽度」这些本该只由字体文件决定的量，
变成了「字体文件 × 栅格化后端」的产物（实测同一份文件跨后端差 68px）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from . import paths

#: 环境变量：显式指定字体族名（CI、特殊机器用）。
#:
#: **名字沿用 aiv 的那个**——两个仓在同一个工作区里，字体验证结果要对得上。
FONT_ENV = "AIV_FONT_FAMILY"

#: 内置字体的族名（**必须唯一**：跟系统字体重名，fontconfig 就在两份里二选一）。
BUNDLED_FAMILY = "AIV Sans CJK SC"

#: 等宽那一族（代码块用）。
BUNDLED_MONO_FAMILY = "AIV Mono CJK SC"

#: 内置字体文件在仓里的位置（**静态拷贝**，与 aiv 那份同字节）。
FONTS_DIR = paths.FONTS_DIR
BUNDLED_PATHS = (
    FONTS_DIR / "AIVSansCJKSC-Regular.otf",
    FONTS_DIR / "AIVSansCJKSC-Bold.otf",
    FONTS_DIR / "AIVMonoCJKSC-Regular.otf",
)

#: 找不到字体时的提示（跟 aiv 那份一致的口径）。
INSTALL_HINT = (
    "装一套中文字体：\n"
    "  内置字体（推荐：两台机器用同一份，跨机版式一致）：\n"
    "    cd aim && python3 scripts/install_font.py\n"
    "  Debian/Ubuntu: sudo apt-get install -y fonts-noto-cjk\n"
    "  Fedora/RHEL:  sudo dnf install google-noto-sans-cjk-fonts\n"
    "  Arch:         sudo pacman -S noto-fonts-cjk\n"
    "  或自带字体：把 NotoSansCJK-Regular.ttc 放进 "
    "~/.local/share/fonts/ 后跑 fc-cache -f\n"
    "也可以用 " + FONT_ENV + "=<族名> 显式指定字体族。"
)

#: 兜底候选（按顺序试）。
FALLBACK_FAMILIES = (
    BUNDLED_FAMILY,
    BUNDLED_MONO_FAMILY,
    "PingFang SC",          # macOS 自带
    "Noto Sans CJK SC",     # Linux 常见
    "Source Han Sans SC",
    "Microsoft YaHei",
    "WenQuanYi Zen Hei",
    "Heiti SC",
    "SimHei",
    "sans-serif",
)


class MissingGlyphs(RuntimeError):
    """字体里没有这些字——**画出来会是豆腐块**，所以直接报错。

    **不是**「渲染不出来就跳过」：跨机版式要对齐，
    一个字缺了，这一版的度量就与别处不同。
    """

    def __init__(self, chars: list[str], family: str) -> None:
        self.chars = list(chars)
        self.family = family
        shown = "".join(self.chars[:40])
        more = f"（共 {len(self.chars)} 个）" if len(self.chars) > 40 else ""
        super().__init__(
            f"字体 {family} 画不出这些字{more}：{shown}\n"
            f"装字体或换族名（{FONT_ENV}）再试。"
        )


def _cairo():
    """惰性取 cairo——只有真要量文字时才 import。"""
    import cairo

    return cairo


@lru_cache(maxsize=1)
def _fc_families() -> frozenset[str] | None:
    """系统里 fontconfig 认得的**所有**族名。

    **不可用时返回 `None`**（macOS 上没有 `fc-list`）——调用方退回宽度判定。

    **为什么不用 `fc-list :family=X` 过滤**：那走 pattern 匹配，
    族名里的 `*` `?` 会被当通配符。列全量再精确比对，没有这种坑。
    """
    exe = shutil.which("fc-list")
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "--format=%{family}\\n"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    names: set[str] = set()
    for line in proc.stdout.splitlines():
        for name in line.split(","):
            name = name.strip()
            if name:
                names.add(name)
    return frozenset(names)


def _resolved_width(family: str, sample: str = "并行解码") -> float:
    """cairo 实际解析该族名后的文本宽度。"""
    cairo = _cairo()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surface)
    select_font(ctx, family)
    ctx.set_font_size(40)
    return ctx.text_extents(sample).width


def family_resolves(family: str) -> bool:
    """这个族名能不能被 cairo 解析出来（而不是静默回退到默认字体）。

    - **fontconfig 在场（Linux）**：直接问它族名在不在。
    - **没有 fontconfig（macOS）**：退回宽度判定。
    """
    families = _fc_families()
    if families is not None:
        return family in families
    try:
        fallback = _resolved_width("__NoSuchFontFamily__")
        return abs(_resolved_width(family) - fallback) > 0.5
    except Exception:
        return False


@lru_cache(maxsize=1)
def resolve_font() -> str:
    """挑一款可用的中文字体族名。"""
    env = os.environ.get(FONT_ENV, "").strip()
    if env:
        return env
    for family in FALLBACK_FAMILIES:
        if family_resolves(family):
            return family
    return BUNDLED_FAMILY


def reset_font_cache() -> None:
    """改完环境变量或装完字体后，让下一次解析重新探测。"""
    resolve_font.cache_clear()
    _fc_families.cache_clear()


def font_family() -> str:
    """给 `ctx.select_font_face()` 用的字体族名。"""
    return resolve_font()


def mono_family() -> str:
    """给**代码块**用的等宽族名；认不到就退回比例字体。"""
    if family_resolves(BUNDLED_MONO_FAMILY):
        return BUNDLED_MONO_FAMILY
    return font_family()


def select_font(ctx, family: str | None = None, *, bold: bool = False) -> None:
    """把 ctx 的字体设成**要画/要量的那一个**，并且**关掉 hinting**。

    **所有地方都必须走这个函数**——直接调 `ctx.select_font_face` 的地方
    一律视为 bug（aim 的测试守着这条）。
    """
    cairo = _cairo()

    options = cairo.FontOptions()
    options.set_hint_style(cairo.HINT_STYLE_NONE)
    options.set_hint_metrics(cairo.HINT_METRICS_OFF)
    ctx.set_font_options(options)

    ctx.select_font_face(
        family if family else font_family(),
        cairo.FONT_SLANT_NORMAL,
        cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
    )


def assert_font_available() -> None:
    """字体不可用时立即失败，避免输出豆腐块。"""
    family = font_family()
    if family_resolves(family):
        return
    raise RuntimeError(
        f"找不到可用的中文字体（当前族名 {family}），拒绝渲染"
        f"（避免输出豆腐块）。\n装字体即可：\n{INSTALL_HINT}\n"
        f"也可以用 {FONT_ENV}=<族名> 显式指定字体族。"
    )


def missing_glyph(ch: str, family: str | None = None) -> bool:
    """这个字符在当前字体里是不是画不出来（会变成豆腐块）。

    **怎么判**：问 cairo 要**字形 id**——`.notdef` 的 id 是 0。
    （不解析 cmap：那是字体文件的内部结构，交给 cairo 更省事也更准。）
    """
    cairo = _cairo()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surface)
    select_font(ctx, family)
    ctx.set_font_size(20)
    glyphs, _clusters, _status = ctx.get_scaled_font().text_to_glyphs(0, 0, ch)
    return not glyphs or glyphs[0].index == 0


def missing_chars(text: str, family: str | None = None) -> list[str]:
    """这段文字里画不出来的字（按出现顺序，不重复）。"""
    out: list[str] = []
    for ch in dict.fromkeys(text):
        if ch.isspace():
            continue
        if missing_glyph(ch, family):
            out.append(ch)
    return out


def check_glyphs(text: str, family: str | None = None) -> None:
    """这段文字里有画不出来的字就**报错**（不画豆腐块）。"""
    face = family if family else font_family()
    missing = missing_chars(text, face)
    if missing:
        raise MissingGlyphs(missing, face)
