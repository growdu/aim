"""形象规格与配色——**这个人的外观事实**，从 `model.json` 读。

**为什么单独一个模块**：眼镜规格、马甲色这些原来**写死在生成脚本里**
（`add_glasses.py` 的 `GLASSES_COLOR`、`stamp_badge.py` 的 `VEST_MAX`），
换人就换不掉——生成出来的还是上一个人的东西。
现在它们是**模型的一部分**：脚本只管读，事实归事实。

## 空 = 还没定

| 没声明 | 后果 |
| --- | --- |
| `look_spec.glasses` | 通用写法：**不戴眼镜**；加眼镜流程直接跳过 |
| `look_spec.vest_color` | 铭牌检测退回**不依赖马甲**的通用路径 |
| `look_spec.badge_text_color` | 用默认的深色（`#1B1B1B`）——白牌上的字要看得清 |
| `look_spec.headset` | prompt 里不写耳麦 |
| `brand.colors` | 品牌片底板退回**框架的中性色**（墨色 / 白） |

**颜色一律是 `#RRGGBB`**（形状由 `aimkit.model.validate` 把关）。
"""
from __future__ import annotations

from .model import Model

#: 铭牌字的默认颜色——白牌上的字要看得清。
#:
#: **刻意不等于任何人的 `badge_text_color`**：这个常量是**框架的兜底**，
#: 而那个是这个人的事实。两者撞上的话，「代码里写死了这个人」就查不出来了。
DEFAULT_BADGE_TEXT = "#1B1B1B"


def hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    """`#RRGGBB` → `(r, g, b)`；不是颜色就返回 `None`。"""
    text = (value or "").strip()
    if len(text) != 7 or not text.startswith("#"):
        return None
    try:
        return (int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16))
    except ValueError:
        return None


def cairo_rgb(colour: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    """`#RRGGBB` → cairo 要的 0~1 三元组。

    **不是颜色就用 `default`**——配色没定是「还没定」，不是崩。
    `default` 是**框架的中性色**（墨色、白），不是任何人的事实。
    """
    rgb = hex_to_rgb(colour)
    if rgb is None:
        return default
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def glasses(model: Model) -> dict:
    """眼镜规格（`style` / `color`）；没声明返回空 dict。"""
    spec = model.look_spec.get("glasses")
    return spec if isinstance(spec, dict) else {}


def has_glasses(model: Model) -> bool:
    """这个人戴不戴眼镜（规格里至少有一项）。"""
    spec = glasses(model)
    return bool((spec.get("style") or "").strip() or (spec.get("color") or "").strip())


def glasses_style(model: Model) -> str:
    """眼镜款式（比如「圆框」「眉线框」）；没声明返回空串。"""
    return (glasses(model).get("style") or "").strip()


def glasses_color(model: Model) -> str:
    """镜框颜色（`#RRGGBB`）；没声明返回空串。"""
    return (glasses(model).get("color") or "").strip()


def vest_rgb(model: Model) -> tuple[int, int, int] | None:
    """马甲/围裙的主色；没声明返回 `None`。

    铭牌在马甲上，所以这个颜色是**铭牌定位的判据**——
    没有它，定位只能退回不依赖马甲的通用路径。
    """
    return hex_to_rgb((model.look_spec.get("vest_color") or "").strip())


def badge_icon_rgb(model: Model) -> tuple[int, int, int] | None:
    """胸口图标色；没声明返回 `None`。"""
    return hex_to_rgb((model.look_spec.get("badge_icon_color") or "").strip())


def badge_text_rgb(model: Model) -> tuple[int, int, int]:
    """铭牌上的字色；没声明用默认的深色。"""
    rgb = hex_to_rgb((model.look_spec.get("badge_text_color") or "").strip())
    return rgb if rgb is not None else hex_to_rgb(DEFAULT_BADGE_TEXT)  # type: ignore[return-value]


def headset(model: Model) -> str:
    """耳麦/麦克风的描述；没声明返回空串。"""
    return (model.look_spec.get("headset") or "").strip()


def vest_color(model: Model) -> str:
    """马甲主色（`#RRGGBB`）；没声明返回空串。"""
    return (model.look_spec.get("vest_color") or "").strip()


def appearance_lines(model: Model, *, include_glasses: bool = True) -> list[str]:
    """形象 prompt 里的「外观要点」——**逐条都来自模型**。

    `look` 是这个人的外观散文（马甲、图标、皮肤…），
    `look_spec` 补上散文说不清的结构化那几样（眼镜、耳麦）。

    **没有的不写**：不戴眼镜就没有眼镜那一行。

    `include_glasses=False` 时跳过眼镜那一条——有些 prompt 要把眼镜
    单独一段写（写得更细），不能重复。
    """
    lines: list[str] = []
    look = model.look.strip()
    if look:
        lines.append(look)
    headset_text = headset(model)
    if headset_text:
        lines.append(f"佩戴{headset_text}")
    if include_glasses:
        style, color = glasses_style(model), glasses_color(model)
        if style or color:
            parts: list[str] = []
            if style:
                parts.append(f"一副{style}眼镜")
            if color:
                parts.append(f"镜框颜色 {color}")
            parts.append("镜片完全透明")
            lines.append("戴" + "，".join(parts))
    return lines


def appearance_prompt(model: Model, *, include_glasses: bool = True) -> str:
    """外观要点的文字版（一行一条 `- `）。"""
    return "\n".join(f"- {line}" for line in
                     appearance_lines(model, include_glasses=include_glasses))

