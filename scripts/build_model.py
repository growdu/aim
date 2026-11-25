#!/usr/bin/env python3
"""写出 `models/<slug>/model.json`——**这个人的唯一契约**。

跑完确认流程（音色定标 → 形象确认 → 人格确认 → 品牌片定稿），
把结果落成一份 JSON。下游（aiv 的渲染与发布）只读这一份。

## 它做什么

1. **归一化**：补齐可空字段的空壳（`identity` 的五项、`voice` 的四段……），
   统一 `schema` 与 `person`。
2. **校验**：形状对不对（`aimkit.model.validate`）。
3. **写出**：**校验通过才写**。

## 它不做什么

**它不发明身份值。** 「站名叫什么」「定位是什么」「受众是谁」——
这些是**这个人的事实**，只能人写。脚本把没写的留成空
（空 = 「还没定」），不拿占位符糊过去。

## 用法

    # 从已有的 model.json 归一化后重写（就地修形状）
    python3 scripts/build_model.py --person growdu --out models/growdu/model.json

    # 从另一份来源生成（--from 缺省就是 --out 本身）
    python3 scripts/build_model.py --person growdu --from /tmp/draft.json \
        --out models/growdu/model.json

    # 只校验，不写
    python3 scripts/build_model.py --person growdu --check
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AIM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AIM_ROOT))

from aimkit import model as model_mod  # noqa: E402
from aimkit import paths  # noqa: E402

#: 可空字段的空壳。**值一律是空**——脚本不发明身份。
EMPTY_IDENTITY = {
    "name": "",
    "role": "",
    "positioning": "",
    "audience": "",
    "taboos": [],
    "series": "",
}

EMPTY_VOICE = {
    "voice_id": "",
    "voice_name": "",
    "pitch": 0,
    "speed": 1.0,
    "emotion": "neutral",
    "measured": {},
    "pronunciation": {},
}

EMPTY_BRAND = {
    "name": "",
    "token": "",
    "tagline": "",
    "site": "",
    "intro_tagline": "",
    "intro_line": "",
    "outro_line": "",
    "outro_narration": "",
    "outro_subtitle": "",
    "outro_title": "",
    "outro_labels": [],
    "share_suffix": "",
    "share_emphasis": "",
    "clips": {},
    "audio": {},
    "windows": "",
}


def normalize(data: dict, person: str) -> dict:
    """补齐空壳、统一 `schema` 与 `person`。

    **只补结构，不补事实**：已有的值一律原样保留（哪怕是空串）。
    """
    out = dict(data)
    out["schema"] = model_mod.SCHEMA_VERSION
    out["person"] = person

    identity = dict(EMPTY_IDENTITY)
    identity.update(out.get("identity") or {})
    out["identity"] = identity

    voice = dict(EMPTY_VOICE)
    voice.update(out.get("voice") or {})
    out["voice"] = voice

    brand = dict(EMPTY_BRAND)
    brand.update(out.get("brand") or {})
    out["brand"] = brand

    out.setdefault("look", "")
    out.setdefault("persona", "")
    out.setdefault("assets", {})
    return out


def load_source(path: Path) -> dict:
    """读来源文件。**没有就当空**（从零开始建一个人）。"""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} 不是合法 JSON：{exc}")
    except OSError as exc:
        raise SystemExit(f"{path} 读不了：{exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="写出 model.json")
    parser.add_argument("--person", required=True, help="这个人的标识（模型目录名）")
    parser.add_argument("--out", help="写到哪里（缺省 models/<person>/model.json）")
    parser.add_argument("--from", dest="source", help="来源文件（缺省就是 --out 本身）")
    parser.add_argument("--check", action="store_true", help="只校验，不写")
    args = parser.parse_args(argv)

    out = Path(args.out) if args.out else paths.model_path(args.person)
    source = Path(args.source) if args.source else out

    raw = load_source(source)

    # **「这个人」只能有一个**。草稿里写着另一个人，而命令行说另一个——
    # 那不是笔误，是拿错了文件。静默改名会把一个人的事实写到别人名下。
    declared = raw.get("person")
    if declared and declared != args.person:
        print(
            f"{source} 里的人是 {declared!r}，命令行说的是 {args.person!r}——"
            f"两份不是同一个人，不写",
            file=sys.stderr,
        )
        return 1

    data = normalize(raw, args.person)
    problems = model_mod.validate(data)

    if problems:
        print(f"{source} 的形状有问题（不写）：", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    if args.check:
        print(f"{out} 形状没问题")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已写出 {out}")
    print(f"  人    {data['person']}")
    print(f"  音色  {data['voice'].get('voice_id') or '（还没定）'}")
    print(f"  形象  {'有' if data['look'] else '（还没定）'}")
    print(f"  人格  {'有' if data['persona'] else '（还没定）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
