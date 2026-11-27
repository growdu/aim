#!/usr/bin/env python3
"""按依赖顺序把「这个人」的素材在本地生成出来。

**素材不入库**——版权与口味是使用者的，仓库只记「它在哪」。
本脚本只管**在本地生成、留在本地**，供回归测试与功能迭代用。
设计见 [`docs/本地素材回路.md`](../docs/本地素材回路.md)。

## 它做什么

1. **先查**：字体装没装、原型图在不在、旁白与台账在不在——缺什么先说清楚。
2. **按依赖顺序跑**：每一步调**现有的脚本**（子进程），不重写任何一步的逻辑。
3. **不重复花钱**：联网耗额度的那几步，产物齐全就跳过。

## 用法

    ./aim assets build                          # 跑完整条链
    ./aim assets build --force                  # 全量重做（含耗额度的那几步）
    ./aim assets build --from "brand render"   # 从这一步开始重做
    ./aim assets build --person <slug>         # 给哪个人生成
    ./aim assets build --library <台账.json>   # 配乐台账（品牌片音轨用）

## 两条不该在这里重写的东西

- **不重写各生成脚本**。子进程调、退出码原样传回——理由跟 `aimkit/cli.py` 一样：
  脚本在 **import 时**就把模型读进模块里，一个进程里 import 几个脚本会撞上
  `sys.modules` 里缓存的旧模块——测出来的是上一个人，而那正是要抓的错。
- **不碰 `doctor`**。它写死了「只报告，不改——`--fix` 不该存在」。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

AIM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AIM_ROOT))

from aimkit import fonts  # noqa: E402
from aimkit import model as model_mod  # noqa: E402
from aimkit import paths as aim_paths  # noqa: E402


@dataclass(frozen=True)
class Step:
    """一步。

    `outputs` 是**这一步的产出**（相对 `models/<slug>/`）——
    产出齐全就说明这一步做过了。

    `costly` = 联网且**消耗生成额度**。只有这类步骤会因「产物齐全」被跳过：
    本地步骤快且确定，每次都跑（改的往往就是它们）。

    `needs` 是**软缺**：缺了就**跳过这一步**，不阻塞整条链
    （沿用渲染自己的降级规矩——素材缺失不是错误）。
    """

    name: str                      # CLI 上的路径，如 "brand render"
    script: str                    # 相对仓根的脚本路径
    outputs: tuple[str, ...] = ()  # 产出（相对 models/<slug>/，`{slug}` 会被替换）
    costly: bool = False           # 联网耗额度？
    needs: tuple[str, ...] = ()    # 软缺（相对 models/<slug>/）


#: 步骤表。**顺序就是依赖顺序**，别随手调。
#:
#: 三处容易排错的地方，钉在这里：
#:
#: 1. **`brand audio` 必须在 `brand render` 前面**——render 把音轨烧进 mp4
#:    （`scripts/brand/render_brand.py`），音轨晚一步，渲出来是静音片。
#: 2. **没有 `character glasses`**——`generate_character.py` 与
#:    `generate_poses.py` 的 prompt 已经带眼镜；`add_glasses.py` 是给**旧素材**
#:    补眼镜的另一条路，带人工关卡（staging → 目视验收 → promote）。
#: 3. **没有 `character badge`**——`generate_character.py` 生成后**自己就盖章了**
#:    （见它的最后一段）。再单独盖一次是在已盖字的白块上盖第二次，
#:    铭牌检测靠白块连通域，第二次可能定位不准。
#:
#: `brand fix-plates` 留着：它修的是**底板 PNG**，而底板在两条线上都已经
#: 没有生产者了（只有消费者），所以这步目前是空转——它自己会说明。
STEPS: tuple[Step, ...] = (
    Step("character generate", "scripts/character/generate_character.py",
         outputs=("character/{slug}_character_2k_nobg.png",
                  "character/{slug}_pose_sheet.png"),
         costly=True),
    Step("character white", "scripts/character/make_white.py"),
    Step("character clear-badge", "scripts/character/clear_badge.py"),
    Step("brand poses", "scripts/brand/generate_poses.py",
         outputs=("brand/assets/{slug}_pose_thumbsup_nobg.png",
                  "brand/assets/{slug}_pose_wave_nobg.png"),
         costly=True),
    Step("brand backgrounds", "scripts/brand/generate_backgrounds.py",
         outputs=("brand/assets/bg_intro.png", "brand/assets/bg_outro.png"),
         costly=True),
    Step("brand audio", "scripts/brand/make_audio_brand.py",
         needs=("brand/audio/voice_intro.mp3", "brand/audio/voice_outro.mp3")),
    Step("brand render", "scripts/brand/render_brand.py"),
    Step("brand fix-plates", "scripts/brand/fix_plates.py"),
)

#: 步骤名 → 步骤。给 `--from` 用。
_BY_NAME = {step.name: step for step in STEPS}


def _model_for(person: str | None) -> model_mod.Model:
    """定下「是哪一份模型」。

    **不猜**：仓里有好几个人时，`model_mod.load()` 会报错列出候选。
    """
    if person:
        path = aim_paths.model_path(person)
        if not path.is_file():
            raise SystemExit(f"没有这个人的模型：{path}")
        return model_mod.load(path)
    return model_mod.load()


def _under(slug: str, relative: str) -> Path:
    return aim_paths.model_dir(slug) / relative.format(slug=slug)


def _done(step: Step, slug: str) -> bool:
    """这一步做过了吗？——**产出全在且非空**才算做过。"""
    if not step.outputs:
        return False
    return all(path.is_file() and path.stat().st_size > 0
               for path in (_under(slug, rel) for rel in step.outputs))


def _missing_needs(step: Step, slug: str) -> list[str]:
    """这一步的**软缺**——哪些前置不在。"""
    return [rel for rel in step.needs
            if not _under(slug, rel).is_file()]


def _library_missing(library: str | None) -> str:
    """配乐台账指不到东西 → 返回一句说明；指得到就返回空串。"""
    ledger = library or os.environ.get("AIV_MUSIC_LIBRARY", "")
    if not ledger:
        return "配乐台账没指（AIV_MUSIC_LIBRARY 或 --library）"
    if not Path(ledger).expanduser().is_file():
        return f"配乐台账指不到东西：{ledger}"
    return ""


def _run(step: Step, env: dict, extra: list[str]) -> int:
    """跑一步。**参数原样转交，退出码原样传回。**"""
    cmd = [sys.executable, str(AIM_ROOT / step.script), *extra]
    print(f"\n=== {step.name} ===")
    proc = subprocess.run(cmd, cwd=str(AIM_ROOT), env=env)
    return proc.returncode


def _preflight(model: model_mod.Model) -> bool:
    """动手之前先查一遍。**硬缺 → 直接停**（后面的跑了也是白花钱）。"""
    # 先把 stdout 冲出去：管道里 stdout 是块缓冲的，
    # 不冲的话 stderr 的报错会跑到人前面（看着像先报错后打头）。
    sys.stdout.flush()

    family = fonts.font_family()
    if not fonts.family_resolves(family):
        print(f"内置字体族 {family} 没装 —— 装它："
              f"python3 scripts/install_font.py", file=sys.stderr)
        print("文字画不出来，后面的都白跑。", file=sys.stderr)
        return False

    source = model.asset("source")
    if source is None or not source.is_file():
        print(f"缺少形象原型参考图："
              f"{source or '（model.json 没声明 assets.source）'}",
              file=sys.stderr)
        print("形象生成是图生图——没有原型图，主形象生成不出来。",
              file=sys.stderr)
        print("修法：把原型参考图放到模型声明的位置"
              "（它是**使用者的素材**，不入库）。", file=sys.stderr)
        return False

    return True


def _notes(model: model_mod.Model, library: str | None) -> list[str]:
    """**软缺**：报出来，不阻塞开工。"""
    notes: list[str] = []

    avatar = model.asset("avatar")
    if avatar is None or not avatar.is_file():
        notes.append(f"头像不在：{avatar or '（没声明）'}——"
                     f"它没有生成路径，是使用者自己的素材")

    missing = _missing_needs(_BY_NAME["brand audio"], model.person)
    if missing:
        notes.append("旁白不在："
                     + "、".join(Path(rel).name for rel in missing)
                     + "——合成不在本仓；缺了就跳过 brand audio，渲出静音片")

    gap = _library_missing(library)
    if gap:
        notes.append(f"{gap}——缺了就跳过 brand audio")

    return notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=("按依赖顺序把这个人的素材在本地生成出来。"
                     "**素材不入库**——生成完留在 models/<slug>/assets/。"))
    parser.add_argument("--person", help="给哪个人生成（缺省 = 仓里那唯一的一个）")
    parser.add_argument("--force", action="store_true",
                        help="无视「产物齐全就跳过」，全量重做（含耗额度的那几步）")
    parser.add_argument("--from", dest="start", metavar="步骤",
                        help="从这一步开始重做（前面的不动）")
    parser.add_argument("--library", help="配乐台账（brand audio 用）")
    args = parser.parse_args(argv)

    try:
        model = _model_for(args.person)
    except model_mod.ModelError as exc:
        print(f"契约读不了：{exc}", file=sys.stderr)
        return 2

    slug = model.person
    env = {**os.environ, model_mod.MODEL_ENV: str(model.path)}

    # `--from` 的名字写错就**报错列出全部步骤名**，不猜。
    start_step = None
    if args.start:
        start_step = _BY_NAME.get(args.start)
        if start_step is None:
            print(f"没有这一步：{args.start}", file=sys.stderr)
            print("可选：", file=sys.stderr)
            for step in STEPS:
                print(f"  - {step.name}", file=sys.stderr)
            return 2

    print(f"人：{model.person}（{model.path}）")
    notes = _notes(model, args.library)
    if notes:
        print()
        print("要先知道的（不影响开工）：")
        for note in notes:
            print(f"  - {note}")

    if not _preflight(model):
        return 1

    steps = STEPS
    if start_step is not None:
        index = [s.name for s in STEPS].index(start_step.name)
        steps = STEPS[index:]

    print()
    print(f"素材目录：{aim_paths.person_assets_dir(slug)}（**不入库**）")
    print(f"要跑 {len(steps)} 步。")

    for step in steps:
        redo = args.force or step is start_step

        # **耗额度**的步骤：产物齐全就跳过——生成要花钱。
        # 本地步骤每次都跑：快、确定，而且改的往往就是它们。
        if step.costly and not redo and _done(step, slug):
            print(f"\n=== {step.name} === 跳过（产物齐全；"
                  f"要重做用 --force）")
            continue

        # **软缺**：缺了就跳过这一步，后面照跑（降级，不阻塞）。
        missing = _missing_needs(step, slug)
        if step.name == "brand audio":
            gap = _library_missing(args.library)
            if gap:
                missing = missing + [gap]
        if missing:
            print(f"\n=== {step.name} === 跳过（缺："
                  + "、".join(missing) + "）")
            continue

        extra: list[str] = []
        if step.name == "brand audio" and args.library:
            extra += ["--library", args.library]

        code = _run(step, env, extra)
        if code != 0:
            print(f"\n{step.name} 退了 {code}——后面的不跑了。", file=sys.stderr)
            return code

    print("\n跑完了。体检一下：")
    print(f"  python3 scripts/doctor.py {model.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
