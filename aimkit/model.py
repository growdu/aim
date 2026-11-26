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
SCHEMA_VERSION = 1

#: 环境变量：指向 `model.json`（CI 与换人时用）。
MODEL_ENV = "AIM_MODEL"

#: 没有指定时用的人。
DEFAULT_SLUG = "growdu"


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

    person = data.get("person")
    if not isinstance(person, str) or not person.strip():
        problems.append("缺 `person`（这个人的标识）")

    voice = data.get("voice")
    if not isinstance(voice, dict):
        problems.append("缺 `voice`（音色段）")
    elif not isinstance(voice.get("voice_id"), str) or not voice["voice_id"].strip():
        problems.append("缺 `voice.voice_id`（音色 id）")

    for key in ("identity", "brand", "assets"):
        if key in data and data[key] is not None and not isinstance(data[key], dict):
            problems.append(f"`{key}` 必须是对象，实际是 {type(data[key]).__name__}")

    for key in ("look", "persona"):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            problems.append(f"`{key}` 必须是文字，实际是 {type(data[key]).__name__}")

    return problems


def model_file(path: str | Path | None = None) -> Path:
    """定下「是哪一份模型」。

    取值顺序：**传参 > 环境变量 `AIM_MODEL` > 默认的人**。
    """
    if path:
        return Path(path).expanduser()
    env = os.environ.get(MODEL_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    return paths.model_path(DEFAULT_SLUG)


def load(path: str | Path | None = None) -> Model:
    """读一份模型。**读不了就报错**——不降级、不返回默认配置。"""
    target = model_file(path)
    if not target.exists():
        raise ModelError(
            f"找不到 model.json：{target}\n"
            f"（设 {MODEL_ENV} 环境变量，或传一个路径；"
            f"默认找 {paths.model_path(DEFAULT_SLUG)}）"
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
        brand=raw.get("brand") or {},
        assets=assets,
        raw=raw,
    )
