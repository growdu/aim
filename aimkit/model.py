"""`model.json` —— **这个人的唯一契约**。

一份 JSON 说清「他是谁」：身份、音色、形象、人格、品牌。
下游读这份文件（**只读文件，不 import 本模块**），把「人」渲染成片。

## 三条硬规矩

1. **元数据里不许出现媒体文件**——只有路径。媒体是素材，**不入库**。
2. **可空的字段就让它空着**——空 = 「还没定」，不是错误。
3. **形状变了就涨 `schema`**——读不懂新形状时**报错退出**，不静默忽略。

## 相对路径的基准

`model.json` 里的相对路径**一律相对 `model.json` 所在目录**
（= `aim/models/<slug>/`）。这样下游不需要知道 aim 仓库根在哪：
基准就是 `Path(model_path).parent`。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

#: 形状版本号。字段变了一定要涨。
#:
#: **2** 增加了 `look_spec`（眼镜规格与配色）与 `brand.backgrounds`
#: （品牌片背景 prompt）——这两样原来写死在生成脚本里，换人就换不掉。
#: **3** 增加了 `brand.colors`（品牌片底板的深色 / 浅色）——
#: 它们原来也是写死在 `render_brand.py` 里的两行常量。
SCHEMA_VERSION = 3

#: 环境变量：指向 `model.json`（CI 与换人时用）。
MODEL_ENV = "AIM_MODEL"


class ModelError(Exception):
    """模型读不了、形状不认识、必填项缺失——**都是硬错误**。

    分两种，和「素材缺失」分得清：

    - 契约坏了（这里）：**报错退出**，不降级。
    - 素材文件不在：不是错误，**降级**（`doctor` 单独报）。
    """


@dataclass(frozen=True)
class Model:
    """一个人。字段都是**已经解析好的**：路径已按 `base` 解成绝对路径。"""

    path: Path
    base: Path
    person: str
    identity: dict = field(default_factory=dict)
    voice: dict = field(default_factory=dict)
    look: str = ""
    persona: str = ""
    look_spec: dict = field(default_factory=dict)
    brand: dict = field(default_factory=dict)
    assets: dict[str, Path | None] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    def asset(self, key: str) -> Path | None:
        """某个素材的路径（`mascot` / `mascot_plain` / `avatar` / `pose_sheet` …）。

        返回的是**声明的位置**，不保证文件存在——素材缺失不是错误。
        """
        return self.assets.get(key)

    def brand_file(self, kind: str, name: str = "") -> Path | None:
        """品牌层某个文件的路径。

        `kind` 取 `clips` / `audio`（`name` 是 `intro` / `outro`）或 `windows`
        （一段路径，`name` 不用给）。
        """
        section = self.brand.get(kind)
        if kind == "windows":
            return resolve(self.base, section if isinstance(section, str) else None)
        if not isinstance(section, dict):
            return None
        return resolve(self.base, section.get(name))

    def background_prompt(self, which: str) -> str:
        """品牌片背景的生成 prompt（`which` 取 `intro` / `outro`）。

        **空 = 还没定**，不是错误——但没有它就生成不出那张背景。
        """
        backgrounds = self.brand.get("backgrounds")
        if not isinstance(backgrounds, dict):
            return ""
        value = backgrounds.get(which)
        return value.strip() if isinstance(value, str) else ""

    def brand_colour(self, which: str) -> str:
        """品牌片底板的配色（`which` 取 `deep` / `light`），`#RRGGBB`。

        **空 = 还没定**，不是错误——渲染时退回框架的中性色。
        """
        colours = self.brand.get("colors")
        if not isinstance(colours, dict):
            return ""
        value = colours.get(which)
        return value.strip() if isinstance(value, str) else ""


def resolve(base: Path, value: str | None) -> Path | None:
    """把模型里的路径解析成绝对路径。

    相对路径的基准是 `base`（= `model.json` 所在目录）。
    空值 → `None`（「还没定」，不是错误）。
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else base / path


def validate(data: object) -> list[str]:
    """检查形状。返回**问题清单**（空 = 合规）。

    只查形状，不查「值好不好」——`identity` 空着是合法的。
    """
    problems: list[str] = []

    if not isinstance(data, dict):
        return [f"model.json 顶层必须是对象，实际是 {type(data).__name__}"]

    schema = data.get("schema")
    if schema is None:
        problems.append("缺 `schema`（形状版本号）")
    elif not isinstance(schema, int) or isinstance(schema, bool):
        problems.append(f"`schema` 必须是整数，实际是 {schema!r}")
    elif schema > SCHEMA_VERSION:
        problems.append(
            f"`schema` 是 {schema}，比本仓认识的 {SCHEMA_VERSION} 新——"
            "升级 aim 再说"
        )
    elif schema < SCHEMA_VERSION:
        problems.append(
            f"`schema` 是 {schema}，本仓认的是 {SCHEMA_VERSION}——"
            "旧形状读不出这个人的眼镜规格、品牌片背景 prompt 与底板配色"
            "（它们在 `look_spec`、`brand.backgrounds` 与 `brand.colors` 里）。"
            f"请补上这几段、把 schema 改成 {SCHEMA_VERSION} 再用"
        )

    person = data.get("person")
    if not isinstance(person, str) or not person.strip():
        problems.append("缺 `person`（这个人的标识）")

    voice = data.get("voice")
    if not isinstance(voice, dict):
        problems.append("缺 `voice`（音色段）")
    elif not isinstance(voice.get("voice_id"), str) or not voice["voice_id"].strip():
        problems.append("缺 `voice.voice_id`（音色 id）")

    for key in ("identity", "brand", "assets", "look_spec"):
        if key in data and data[key] is not None and not isinstance(data[key], dict):
            problems.append(f"`{key}` 必须是对象，实际是 {type(data[key]).__name__}")

    for key in ("look", "persona"):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            problems.append(f"`{key}` 必须是文字，实际是 {type(data[key]).__name__}")

    problems.extend(_look_spec_problems(data.get("look_spec")))

    brand = data.get("brand")
    if isinstance(brand, dict):
        backgrounds = brand.get("backgrounds")
        if backgrounds is not None and not isinstance(backgrounds, dict):
            problems.append(
                "`brand.backgrounds` 必须是对象，实际是 "
                f"{type(backgrounds).__name__}"
            )
        elif isinstance(backgrounds, dict):
            for which, value in backgrounds.items():
                if value is not None and not isinstance(value, str):
                    problems.append(
                        f"`brand.backgrounds.{which}` 必须是文字（生成 prompt），"
                        f"实际是 {type(value).__name__}"
                    )
        problems.extend(_brand_colour_problems(brand.get("colors")))

    return problems


def _brand_colour_problems(colours: object) -> list[str]:
    """查 `brand.colors` 的形状。

    **空 = 还没定**（渲染退回中性色），非空必须是 `#RRGGBB`。
    """
    if colours is None:
        return []
    if not isinstance(colours, dict):
        return [f"`brand.colors` 必须是对象，实际是 {type(colours).__name__}"]

    problems: list[str] = []
    for which, value in colours.items():
        problems.extend(_color_problems(f"brand.colors.{which}", value))
    return problems


def _look_spec_problems(look_spec: object) -> list[str]:
    """查 `look_spec` 的形状。

    **颜色一律是 `#RRGGBB`**——颜色要喂给 cairo 与 numpy，
    写成 `rgb(...)` 或漏了 `#` 都会在渲染那一刻才炸。
    """
    if not isinstance(look_spec, dict):
        return []

    problems: list[str] = []
    glasses = look_spec.get("glasses")
    if glasses is not None and not isinstance(glasses, dict):
        problems.append(
            f"`look_spec.glasses` 必须是对象，实际是 {type(glasses).__name__}"
        )
    elif isinstance(glasses, dict):
        for key in ("style", "color"):
            value = glasses.get(key)
            if value is not None and not isinstance(value, str):
                problems.append(f"`look_spec.glasses.{key}` 必须是文字")
        problems.extend(_color_problems("look_spec.glasses.color",
                                       glasses.get("color")))

    for key in ("vest_color", "badge_icon_color", "badge_text_color"):
        problems.extend(_color_problems(f"look_spec.{key}", look_spec.get(key)))

    headset = look_spec.get("headset")
    if headset is not None and not isinstance(headset, str):
        problems.append("`look_spec.headset` 必须是文字")

    return problems


def _color_problems(label: str, value: object) -> list[str]:
    """查一个颜色值：空 = 还没定；非空必须是 `#RRGGBB`。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return []
    if not isinstance(value, str):
        return [f"`{label}` 必须是颜色文字，实际是 {type(value).__name__}"]
    text = value.strip()
    if not (len(text) == 7 and text.startswith("#")
            and all(c in "0123456789abcdefABCDEF" for c in text[1:])):
        return [f"`{label}` 必须是 `#RRGGBB` 形式的颜色，实际是 {text!r}"]
    return []


def _model_candidates() -> list[Path]:
    """仓里有几个人的模型（按目录名排好序）。"""
    if not paths.MODELS_DIR.is_dir():
        return []
    found: list[Path] = []
    for entry in sorted(paths.MODELS_DIR.iterdir()):
        candidate = entry / "model.json"
        if candidate.is_file():
            found.append(candidate)
    return found


def model_file(path: str | Path | None = None) -> Path:
    """定下「是哪一份模型」。

    取值顺序：**传参 > 环境变量 `AIM_MODEL` > 仓里唯一的那个人**。

    **仓里有好几个人时绝不猜。** 猜错就是拿别人的事实去生成这个人的
    素材与片子——那是**静默的错误**，比报错难查得多。
    """
    if path:
        return Path(path).expanduser()
    env = os.environ.get(MODEL_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    candidates = _model_candidates()
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ModelError(
            f"仓里没有人的模型（{paths.MODELS_DIR} 下没有 model.json）。\n"
            f"建一个人：python3 scripts/build_model.py --person <slug> "
            f"--out {paths.MODELS_DIR}/<slug>/model.json"
        )
    listed = "\n".join(f"  - {c}" for c in candidates)
    raise ModelError(
        f"仓里有好几个人，不猜用哪个：\n{listed}\n"
        f"指一个：设环境变量 {MODEL_ENV}=<上面某个 model.json 的路径>"
    )


def load(path: str | Path | None = None) -> Model:
    """读一份模型。**读不了就报错**——不降级、不返回默认配置。"""
    target = model_file(path)
    if not target.exists():
        raise ModelError(
            f"找不到 model.json：{target}\n"
            f"（设 {MODEL_ENV} 环境变量，或传一个路径）"
        )
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModelError(f"model.json 不是合法 JSON：{target}（{exc}）") from exc
    except OSError as exc:
        raise ModelError(f"model.json 读不了：{target}（{exc}）") from exc

    problems = validate(raw)
    if problems:
        listed = "\n".join(f"  - {p}" for p in problems)
        raise ModelError(f"model.json 形状不对：{target}\n{listed}")

    base = target.parent
    assets_raw = raw.get("assets") or {}
    assets = {
        key: resolve(base, value)
        for key, value in assets_raw.items()
    }

    return Model(
        path=target,
        base=base,
        person=raw["person"],
        identity=raw.get("identity") or {},
        voice=raw.get("voice") or {},
        look=raw.get("look") or "",
        persona=raw.get("persona") or "",
        look_spec=raw.get("look_spec") or {},
        brand=raw.get("brand") or {},
        assets=assets,
        raw=raw,
    )
