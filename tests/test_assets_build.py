"""`build_assets.py`——本地素材回路的编排器。

**为什么要有这条守卫**：这条链**花钱**（联网生成要消耗额度）、
**有顺序**（顺序错了渲出静音片）、**还牵着人工关卡**（眼镜的三段式流程）。
三样都容易在重构里被弄坏，而坏的方式都很安静——画面照样生成、
时长照样对。

所以守四件事：

1. **步序**：`brand audio` 必须在 `brand render` 前面——
   render 把音轨烧进 mp4，音轨晚一步就是静音片。
2. **链上不该有的那两步**：`character glasses` 与 `character badge`
   都不在链上（各有各的理由，见 `scripts/build_assets.py` 的注释）。
3. **每一步调的都是命令表里的脚本**——链跟 CLI 说的是同一套实现。
4. **缺东西时别花钱**：原型图不在就**一步都不跑**，退出非 0。
"""
from __future__ import annotations

import json
import subprocess

import pytest

from aimkit import cli as cli_mod
from aimkit import model as model_mod

from _scripts import load_script


def _build_assets():
    return load_script("build_assets.py", "aim_script_build_assets")


def _names(steps) -> list[str]:
    return [step.name for step in steps]


# ---- 步序 ---------------------------------------------------------------


def test_the_audio_comes_before_the_render():
    """**音轨在渲片之前。**

    `render_brand.py` 把音轨烧进 mp4——音轨晚一步，渲出来是静音片，
    而且得再渲一遍。教程曾经把这两步排反了。
    """
    steps = _names(_build_assets().STEPS)

    assert "brand audio" in steps, f"链上没有 brand audio：{steps}"
    assert "brand render" in steps, f"链上没有 brand render：{steps}"
    assert steps.index("brand audio") < steps.index("brand render"), (
        f"brand audio 必须在 brand render 前面——render 把音轨烧进 mp4，"
        f"反了渲出静音片。现在的顺序：{steps}"
    )


def test_the_glasses_and_the_badge_are_not_in_the_chain():
    """**眼镜与盖章都不在链上。**

    - 眼镜：`generate_character.py` 与 `generate_poses.py` 的 prompt
      已经带眼镜；`add_glasses.py` 是给旧素材补眼镜的另一条路，
      带人工关卡（staging → 目视验收 → promote）。
    - 盖章：`generate_character.py` 生成后**自己就盖章了**；
      再盖一次是在已盖字的白块上盖第二次，铭牌检测靠白块连通域，
      第二次可能定位不准。
    """
    steps = _names(_build_assets().STEPS)

    assert "character glasses" not in steps, (
        f"眼镜不在链上——它带人工关卡：{steps}"
    )
    assert "character badge" not in steps, (
        f"盖章不在链上——generate 自己就盖了：{steps}"
    )


# ---- 链跟 CLI 是同一套实现 ----------------------------------------------


def test_every_step_calls_a_registered_script():
    """链上每一步调的脚本，**都得在命令表里**。

    不在命令表里的脚本 = 只能用内部路径调它 = 交付形式缺一块。
    """
    registered = {command.script for command in cli_mod.COMMANDS}

    for step in _build_assets().STEPS:
        assert step.script in registered, (
            f"{step.name} 调的 {step.script} 不在命令表里——"
            f"链跟 CLI 不是同一套实现了"
        )


def test_the_build_command_is_registered():
    """`aim assets build` 得叫得到。"""
    paths = {command.path for command in cli_mod.COMMANDS}
    assert "assets build" in paths, f"命令表里没有 assets build：{sorted(paths)}"


# ---- 缺东西别花钱 -------------------------------------------------------


def _model_without_source(tmp_path, monkeypatch) -> None:
    """指一份「原型图不在」的模型。"""
    source = json.loads(
        (model_mod.paths.AIM_ROOT / "models" / "growdu" / "model.json")
        .read_text(encoding="utf-8")
    )
    source["assets"]["source"] = "assets/character/根本没有这张图.jpeg"
    target = tmp_path / "model.json"
    target.write_text(json.dumps(source, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))


def test_it_does_not_spend_anything_when_the_source_is_missing(
        tmp_path, monkeypatch, capsys):
    """**原型图不在 → 一步都不跑**，退出非 0，说清楚缺什么。

    形象生成是**图生图**：没有原型参考图，主形象生成不出来。
    这时候往下跑就是白花钱——所以必须在跑之前就停。
    """
    _model_without_source(tmp_path, monkeypatch)

    ran: list[list[str]] = []
    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):
        ran.append(list(cmd))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)

    code = _build_assets().main([])

    assert code != 0, "原型图不在却退 0——那是要往下游跑的"
    # 只看**脚本**有没有被调起来：字体自检跑 `fc-list` 是**查**，
    # 不是生成——查不花钱，生成才花钱。
    ran_steps = [cmd for cmd in ran if any("scripts/" in part for part in cmd)]
    assert not ran_steps, f"原型图不在还跑了这些：{ran_steps}"

    err = capsys.readouterr().err
    assert "原型" in err, f"没说清楚缺的是原型图：\n{err}"


def test_an_unknown_step_name_lists_the_real_ones(tmp_path, monkeypatch,
                                                  capsys):
    """`--from` 的名字写错 → **列出全部步骤名**，不猜。"""
    _model_without_source(tmp_path, monkeypatch)

    code = _build_assets().main(["--from", "brand renderr"])

    assert code != 0, "步骤名写错却退 0"
    err = capsys.readouterr().err
    assert "brand render" in err, f"没列出真正的步骤名：\n{err}"


# ---- 步骤表本身 ---------------------------------------------------------


def test_the_steps_all_exist_as_scripts():
    """每一步指着的脚本都得在仓里。"""
    from aimkit import paths

    for step in _build_assets().STEPS:
        script = paths.AIM_ROOT / step.script
        assert script.is_file(), f"{step.name} 指的脚本不在：{script}"


def test_the_costly_steps_are_the_ones_that_spend():
    """**只有联网生成的那几步是 costly。**

    costly = 产物齐全就可以跳过（省额度）。
    本地步骤不标 costly——它们每次都跑（快、确定，而且改的往往就是它们）。
    """
    costly = _names([s for s in _build_assets().STEPS if s.costly])

    assert costly == ["character generate", "brand poses", "brand backgrounds"], (
        f"耗额度的步骤变了：{costly}"
    )


def test_every_costly_step_declares_what_it_produces():
    """**耗额度的步骤必须声明产出**——否则没法判断「做过了没有」。"""
    for step in _build_assets().STEPS:
        if step.costly:
            assert step.outputs, f"{step.name} 是耗额度的，却没说产出什么"
            for rel in step.outputs:
                assert "{slug}" in rel or "/" in rel, (
                    f"{step.name} 的产出路径不对：{rel}"
                )
