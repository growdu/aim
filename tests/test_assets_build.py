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
import os
import subprocess

import pytest

from aimkit import cli as cli_mod
from aimkit import model as model_mod
from aimkit import paths as aim_paths

from _scripts import load_script, real_asset_paths


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


def test_the_glasses_are_not_in_the_chain():
    """**眼镜不在链上。**

    `generate_character.py` 与 `generate_poses.py` 的 prompt 已经带眼镜
    （`look_spec.glasses` 声明了就写进 prompt）；`add_glasses.py` 是给
    **旧素材**补眼镜的另一条路，带人工关卡（staging → 目视验收 → promote）。
    """
    steps = _names(_build_assets().STEPS)

    assert "character glasses" not in steps, (
        f"眼镜不在链上——它带人工关卡：{steps}"
    )


def test_the_badge_comes_after_the_white_and_after_the_poses():
    """**盖章在白底合成之后，也在姿态生成之后。**

    - `make_white` 从透明底版**重写**白底版，章得重新盖一遍；
    - 姿态图是 `brand poses` 那一步才生成的——盖章排在它前面，
      姿态图压根还不存在，那一步永远盖不到它。

    看着多余（`generate` 生成后自己就盖了），但它保两件事：
    `generate` 被跳过时品牌词照样最新；改了 `brand.token` 再跑一遍章会跟着改。
    """
    steps = _names(_build_assets().STEPS)

    assert "character badge" in steps, f"链上没有盖章：{steps}"
    assert steps.index("character white") < steps.index("character badge"), (
        f"盖章要在白底合成之后——make_white 会重写白底版：{steps}"
    )
    assert steps.index("brand poses") < steps.index("character badge"), (
        f"盖章要在姿态生成之后——姿态图是那一步才有的：{steps}"
    )


def test_the_clearing_comes_after_the_generation():
    """**抹铭牌在生成之后。**

    抹的是「带铭牌那份」——生成那一步自己就盖了章，所以抹要在它后面。
    """
    steps = _names(_build_assets().STEPS)

    assert "character clear-badge" in steps, f"链上没有抹铭牌：{steps}"
    assert steps.index("character generate") < steps.index("character clear-badge"), (
        f"抹铭牌要在生成之后——抹的是带铭牌那份：{steps}"
    )


# ---- 路径：素材在哪，链与测试得看同一个地方 -------------------------------


def test_the_step_paths_resolve_under_the_person_asset_dir():
    """步骤表里的路径，基准是 `models/<slug>/assets/`。

    以前基准是 `models/<slug>/`，**少了一层**——于是「产出齐全就跳过」
    永远不成立：每跑一次链，耗额度的步骤都被重做一遍，**白烧额度**，
    而且屏幕上什么异常都看不出来。
    """
    build = _build_assets()
    slug = model_mod.load().person
    base = aim_paths.person_assets_dir(slug)

    for step in build.STEPS:
        for rel in step.outputs + step.needs + step.needs_badge:
            path = build._under(slug, rel)
            assert base in path.parents, (
                f"{step.name} 的 {rel} 解析到了 {path}——"
                f"不在 {base} 底下，跳过判断就永远不成立"
            )


def test_the_chain_and_the_tests_look_at_the_same_assets():
    """**链上的产出 == 测试验的素材。**

    以前三个测试文件自己拼 `person_assets_dir/"brand/..."`，而品牌片的
    脚本把素材放在 `brand/assets/` 下——**少一层**。于是那些用例永远在
    找一条不存在的路径、永远 skip，等于写了但从没跑过。
    """
    build = _build_assets()
    slug = model_mod.load().person
    expected = set(real_asset_paths(slug))

    steps = {step.name: step for step in build.STEPS}
    outputs = {build._under(slug, rel) for rel in steps["brand poses"].outputs}
    pose_paths = {p for p in expected if "pose" in p.name}
    assert outputs == pose_paths, (
        f"链上的姿态产出与测试看的位置对不上："
        f"{sorted(str(p) for p in outputs)} vs {sorted(str(p) for p in pose_paths)}"
    )

    stamp = load_script("character/stamp_badge.py")
    assert expected <= set(stamp.DEFAULT_TARGETS), (
        f"盖章脚本的默认目标少了测试要验的素材：{stamp.DEFAULT_TARGETS}"
    )


# ---- 产物合不合格：文件在 ≠ 合格 -----------------------------------------


def _env_for(slug: str) -> dict:
    return {
        **os.environ,
        model_mod.MODEL_ENV: str(aim_paths.model_path(slug)),
    }


def test_a_product_with_the_brand_word_is_done():
    """产出齐全**且带品牌词** → 这一步算做过了（省额度）。"""
    build = _build_assets()
    slug = model_mod.load().person
    env = _env_for(slug)

    step = build.STEPS[[s.name for s in build.STEPS].index("brand poses")]
    if not all(build._under(slug, rel).exists() for rel in step.outputs):
        pytest.skip("本机没有姿态素材，跳过")

    assert build._done(step, slug, env) is True, \
        "产出齐了、带品牌词，却判成没做完——链会白重做一遍"


def test_a_product_without_the_brand_word_is_not_done(tmp_path, monkeypatch):
    """产出在、但**没带品牌词** → 这步不算做完，链要重做它。

    模型有的时候不画胸口那块白色铭牌（实测 2026-11-27 那批两个姿态
    都没画，画面上只剩胸口那枚琥珀黄图标）。那种图渲出来的片子
    没有品牌词——不能当成合格的产物，更不能悄悄流到品牌片里去。
    """
    build = _build_assets()
    slug = model_mod.load().person
    from PIL import Image

    asset = tmp_path / "pose.png"
    Image.new("RGBA", (256, 256), (12, 24, 48, 255)).save(asset)
    monkeypatch.setattr(build, "_under", lambda s, rel: asset)

    step = build.Step("brand poses", "scripts/brand/generate_poses.py",
                       outputs=("pose.png",), needs_badge=("pose.png",),
                       costly=True)

    assert build._done(step, slug, _env_for(slug)) is False, \
        "没带品牌词的产物被判成做过了——坏素材会一路流到品牌片"


def test_the_pose_step_declares_that_its_outputs_need_the_brand_word():
    """姿态素材必须带品牌词——所以「做完了」的判据里要算上它。"""
    build = _build_assets()
    steps = {step.name: step for step in build.STEPS}

    poses = steps["brand poses"]
    assert set(poses.needs_badge) == set(poses.outputs), (
        f"brand poses 的产出都得带品牌词：{poses}"
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
