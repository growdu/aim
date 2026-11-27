"""`aim` —— **命令行入口**。

**为什么要有它。** 交付形式是「一个仓 + 一组命令行脚本」——
但**散着的脚本不是 CLI**：别的工具、别的 agent 没法稳定地调它们
（路径要自己拼、参数要自己查、退出码得自己认）。
一个入口给**一个名字**：`aim <阶段> <动作> [参数…]`。

## 实现只有一份

命令表指向**现有的脚本**，参数**原样转交**——
不重写逻辑、不重写 argparse、不重写退出码。
脚本是实现，这个入口是**门面**。

## 为什么用子进程而不是 import

脚本在 **import 时就把模型读进模块里**（`model_mod.load()`），
一个进程里 import 几个脚本会撞上 `sys.modules` 里缓存的旧模块——
测出来的是上一个人，而那正是要抓的错。
子进程一劳永逸：每个脚本一个干净的进程，退出码原样传回来。
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from . import paths

AIM_ROOT = paths.AIM_ROOT


@dataclass(frozen=True)
class Command:
    """一条命令：叫什么、跑哪个脚本、干什么。"""

    path: str          # CLI 上的名字，如 "character badge"
    script: str        # 相对仓根的脚本路径
    summary: str       # 一句话：它是干什么的


#: 命令表。**每个带 `__main__` 的脚本都要在这儿**（`tests/test_cli.py` 盯着）。
COMMANDS: tuple[Command, ...] = (
    Command("doctor", "scripts/doctor.py",
            "体检：这个人的契约与素材齐不齐（只报告，不改）"),
    Command("model build", "scripts/build_model.py",
            "把确认结论归一化成 model.json（校验通过才写）"),
    Command("font install", "scripts/install_font.py",
            "装内置字体子集（跨机版式一致靠它）"),
    Command("assets build", "scripts/build_assets.py",
            "按依赖顺序把这个人的素材在本地生成出来（素材不入库）"),
    Command("character generate", "scripts/character/generate_character.py",
            "从形象原型生成主形象与 6 姿态表（消耗生成额度）"),
    Command("character glasses", "scripts/character/add_glasses.py",
            "给形象戴眼镜（没声明眼镜就整体跳过）"),
    Command("character badge", "scripts/character/stamp_badge.py",
            "盖铭牌：刷白那块白矩形，再用真实字体写上品牌词"),
    Command("character clear-badge", "scripts/character/clear_badge.py",
            "抹掉铭牌，产出「无标牌」素材"),
    Command("character white", "scripts/character/make_white.py",
            "把透明底素材铺成白底（合成，不重新生成）"),
    Command("brand poses", "scripts/brand/generate_poses.py",
            "生成品牌片用的点赞 / 挥手姿态素材"),
    Command("brand backgrounds", "scripts/brand/generate_backgrounds.py",
            "生成品牌片用的两张 AI 背景（含语义验收）"),
    Command("brand render", "scripts/brand/render_brand.py",
            "渲染品牌片头 / 片尾（2.833s，1920×1080）"),
    Command("brand fix-plates", "scripts/brand/fix_plates.py",
            "修复底板里被 16:9 裁断的文字（真实字体重排）"),
    Command("brand audio", "scripts/brand/make_audio_brand.py",
            "按配乐窗口切曲混音，产出成品音轨"),
    Command("voice measure", "scripts/voice/measure_voice.py",
            "量测参照录音的音色特征"),
    Command("voice check", "scripts/voice/check_pronunciation.py",
            "查多音字读音对不对"),
)

#: 分组（`character` / `brand` / …）——**只算两段以上的命令**。
#:
#: `doctor` 是**单段命令**，不是一组：它没有「动作」可列。
GROUPS = tuple(dict.fromkeys(
    c.path.split()[0] for c in COMMANDS if len(c.path.split()) > 1
))


def _find(name: str) -> Command | None:
    for command in COMMANDS:
        if command.path == name:
            return command
    return None


def _usage() -> str:
    lines = ["用法：aim <命令> [参数…]", "", "命令："]
    width = max(len(c.path) for c in COMMANDS)
    for command in COMMANDS:
        lines.append(f"  {command.path.ljust(width)}  {command.summary}")
    lines += [
        "",
        "每个命令的完整参数：aim <命令> --help",
        "（参数原样转交给脚本，退出码也是脚本的）",
    ]
    return "\n".join(lines)


def _group_usage(group: str) -> str:
    items = [c for c in COMMANDS if c.path.split()[0] == group]
    lines = [f"用法：aim {group} <动作> [参数…]", "", f"{group} 的动作："]
    width = max(len(c.path.split(maxsplit=1)[1]) for c in items)
    for command in items:
        action = command.path.split(maxsplit=1)[1]
        lines.append(f"  {action.ljust(width)}  {command.summary}")
    lines += ["", f"完整参数：aim {group} <动作> --help"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help", "help"):
        print(_usage())
        return 0

    if argv[0] in ("-V", "--version"):
        from . import model as model_mod
        print(f"aim schema {model_mod.SCHEMA_VERSION}")
        return 0

    # `aim <组>` —— 列出这一组的动作
    if len(argv) == 1 and argv[0] in GROUPS:
        print(_group_usage(argv[0]))
        return 0

    # `aim <组> <动作>` —— 找到一个命令
    if len(argv) >= 2 and argv[0] in GROUPS:
        command = _find(f"{argv[0]} {argv[1]}")
        if command is None:
            print(f"没有这个命令：aim {argv[0]} {argv[1]}", file=sys.stderr)
            print(_group_usage(argv[0]), file=sys.stderr)
            return 2
        rest = argv[2:]
    else:
        command = _find(argv[0])
        if command is None:
            print(f"没有这个命令：{argv[0]}", file=sys.stderr)
            print(_usage(), file=sys.stderr)
            return 2
        rest = argv[1:]

    script = AIM_ROOT / command.script
    if not script.is_file():
        print(f"脚本不在：{script}", file=sys.stderr)
        return 2

    # 参数原样转交；退出码原样传回。
    proc = subprocess.run([sys.executable, str(script), *rest], cwd=str(AIM_ROOT))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
