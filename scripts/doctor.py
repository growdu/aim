#!/usr/bin/env python3
"""体检：这个人的契约与素材齐不齐。

**为什么要有这个。** 契约坏了是硬错误（脚本直接报错退出）；
**素材缺失不是错误**——降级照做，画面照样出得来，但没人知道少了什么。
`doctor` 就是把「缺了什么」单独报出来的那条路。

它**只报告，不改**：体检不是修复，`--fix` 不该存在——
「素材不见了」的原因是多样的（没生成 / 路径写错 / 素材在别的机器上），
自作主张地补一个空文件，只会把问题盖住。

用法：
  python3 scripts/doctor.py                # 体检当前这个人
  python3 scripts/doctor.py <model.json>   # 体检指定的人

退出码：齐了是 0，缺东西是 1（坏契约是 2）。
"""
from __future__ import annotations

import sys
from pathlib import Path

AIM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AIM_ROOT))

from aimkit import fonts  # noqa: E402
from aimkit import look as look_spec  # noqa: E402
from aimkit import model as model_mod  # noqa: E402
from aimkit import paths as aim_paths  # noqa: E402

OK = "  ok  "
MISS = "  --  "


def _report_assets(model: model_mod.Model) -> int:
    """素材段声明的文件——在不在。"""
    missing = 0
    print("素材")
    if not model.assets:
        print(f"{MISS}一个都没声明")
        return 1
    for key in sorted(model.assets):
        path = model.asset(key)
        if path is None:
            print(f"{MISS}{key}：没声明路径")
            missing += 1
            continue
        if path.exists():
            print(f"{OK}{key}：{path.name}")
        else:
            print(f"{MISS}{key}：{path} 不在")
            missing += 1
    return missing


def _report_brand(model: model_mod.Model) -> int:
    """品牌片要用的那些文件——在不在。"""
    missing = 0
    print("品牌片")
    for kind, name in (("clips", "intro"), ("clips", "outro"),
                        ("audio", "intro"), ("audio", "outro")):
        path = model.brand_file(kind, name)
        label = f"{kind}.{name}"
        if path is None:
            print(f"{MISS}{label}：没声明")
            missing += 1
        elif path.exists():
            print(f"{OK}{label}：{path.name}")
        else:
            print(f"{MISS}{label}：{path} 不在")
            missing += 1
    windows = model.brand_file("windows")
    if windows is None:
        print(f"{MISS}windows：没声明")
        missing += 1
    elif windows.exists():
        print(f"{OK}windows：{windows.name}")
    else:
        print(f"{MISS}windows：{windows} 不在")
        missing += 1
    return missing


def _report_look(model: model_mod.Model) -> int:
    """形象规格——**定了没有**。空 = 还没定，不是错误。"""
    print("形象规格")
    undetermined = 0
    style = look_spec.glasses_style(model)
    color = look_spec.glasses_color(model)
    if style or color:
        print(f"{OK}眼镜：{style or '（没写款式）'} / {color or '（没写颜色）'}")
    else:
        print(f"{MISS}眼镜：没声明 → 这个人不戴眼镜（加眼镜流程会跳过）")
    for label, value in (("衣服主色", look_spec.vest_color(model)),
                         ("胸口图标色", model.look_spec.get("badge_icon_color", "")),
                         ("铭牌字色", model.look_spec.get("badge_text_color", "")),
                         ("耳麦", look_spec.headset(model))):
        if value:
            print(f"{OK}{label}：{value}")
        else:
            print(f"{MISS}{label}：还没定")
            undetermined += 1
    return undetermined


def _report_backgrounds(model: model_mod.Model) -> int:
    """品牌片两张背景的生成 prompt——定了没有。"""
    print("背景")
    missing = 0
    for which in ("intro", "outro"):
        prompt = model.background_prompt(which)
        if prompt:
            print(f"{OK}{which}：prompt 已定（{len(prompt)} 字）")
        else:
            print(f"{MISS}{which}：prompt 还没定（生成脚本会拒绝出货）")
            missing += 1
    return missing


def _report_colours(model: model_mod.Model) -> int:
    """品牌片底板的配色——定了没有。空 = 还没定（渲染退回中性色）。"""
    print("底板配色")
    missing = 0
    for which, label in (("deep", "深色"), ("light", "浅色")):
        value = model.brand_colour(which)
        if value:
            print(f"{OK}{label}：{value}")
        else:
            print(f"{MISS}{label}：还没定（渲染退回中性色）")
            missing += 1
    return missing


def _report_fonts() -> int:
    """内置字体——装没装。缺了文字就是乱码。"""
    print("字体")
    family = fonts.font_family()
    if fonts.family_resolves(family):
        print(f"{OK}字体族：{family}")
        return 0
    print(f"{MISS}字体族 {family} 没装 —— 装它：python3 scripts/install_font.py")
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        model = model_mod.load(argv[0] if argv else None)
    except model_mod.ModelError as exc:
        print(f"契约读不了：{exc}", file=sys.stderr)
        return 2

    print(f"人：{model.person}（{model.path}）")
    print(f"schema：{model.raw.get('schema')}")
    print()

    missing = 0
    missing += _report_assets(model)
    print()
    missing += _report_brand(model)
    print()
    missing += _report_look(model)
    print()
    missing += _report_backgrounds(model)
    print()
    missing += _report_colours(model)
    print()
    missing += _report_fonts()

    print()
    if missing:
        print(f"缺 {missing} 处。缺素材不是错误（渲染会降级），但成片会缺东西。")
        return 1
    print("齐了。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
