"""品牌片**生成脚本**的结构性守卫。

品牌片是「这个人的素材」，所以脚本跟着人走。
守卫也得跟着走：脚本跑在别人的机器上、产物直接进成片，
一旦结构变了，**画面照常生成、时长照常对**，没有任何报错。

盯的是三件最容易静默出错的事：

1. **姿态素材必须补一次镜框修补**——模型戴上方形眼镜后会在镜框或镜腿上
   贴一小块白色小铭牌（实测写着品牌词）。prompt 里禁了也不听，
   所以图生图之后必须再补一次局部修补。
2. **背景必须一次生成一个连续空间**——AI 宽幅背景的固定毛病是左右两个
   场景硬拼。羽化糊不掉缝，正解是重新生成。
3. **背景生成完必须过语义验收**——像素判据证明不了「这是不是一整个空间」
   （试过两种都误报），所以交给能看图的模型问一句。

另外两条盯着**成品音轨的混音脚本**：窗口不相接就拒产，淡出要短。
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aimkit import model as model_mod
from aimkit import paths as aim_paths

from _scripts import load_script

_MODEL = model_mod.load()
SLUG = _MODEL.person

BRAND_SCRIPTS = aim_paths.SCRIPTS_DIR / "brand"


# ---------------------------------------------------------------- 姿态


def test_the_pose_script_repairs_the_glasses_badge():
    """姿态素材必须走一次镜框局部修补。

    模型戴上方形眼镜后有个固定毛病：会在镜框或镜腿上贴一小块白色小
    铭牌（实测写着品牌词）。prompt 里禁了也不听，所以图生图之后必须
    再补一次局部修补。
    """
    tree = ast.parse(
        (BRAND_SCRIPTS / "generate_poses.py").read_text(encoding="utf-8"))
    imported = any(
        isinstance(node, ast.ImportFrom) and node.module == "add_glasses"
        and any(alias.name == "cleanup_glasses" for alias in node.names)
        for node in ast.walk(tree)
    )
    called = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "cleanup_glasses"
        for node in ast.walk(tree)
    )
    assert imported and called, (
        "generate_poses.py 没有走 cleanup_glasses——镜框上的白色小铭牌"
        "会留在素材上"
    )


# ---------------------------------------------------------------- 背景


def _background_source() -> str:
    return (BRAND_SCRIPTS / "generate_backgrounds.py").read_text(encoding="utf-8")


def test_the_background_script_makes_one_continuous_space():
    """背景必须**一次生成一个连续空间**，不许拼两个半张。

    AI 宽幅背景的固定毛病就是左右两个场景硬拼。羽化糊不掉缝，正解是
    用「单一连续空间」的 prompt 重新生成——所以 prompt 里必须写死这一
    条，而且不许把两张图拼起来。
    """
    source = _background_source()
    tree = ast.parse(source)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            name = getattr(node.func, "id", "")
        if name in {"hstack", "vstack", "concat", "paste", "tile"}:
            offenders.append(f"{name}（第 {node.lineno} 行）")
    assert offenders == [], (
        f"背景脚本里有把图拼起来的调用：{offenders}——"
        f"拼出来的接缝羽化糊不掉"
    )

    assert "单一连续空间" in source, "prompt 里必须写死「单一连续空间」"
    assert "不要接缝" in source, "prompt 里必须写死「不要接缝」"


def test_the_background_script_verifies_its_own_output():
    """背景生成完必须过**语义验收**，不许直接出货。

    像素判据证明不了「这是不是一整个空间」——试过两种都误报（楼群边缘、
    走廊尽头的亮光都被当成了接缝）。这条交给能看图的模型问。
    """
    tree = ast.parse(_background_source())
    called = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "verify_continuous_space"
        for node in ast.walk(tree)
    )
    assert called, "背景脚本没有做语义验收——拼缝的背景会直接出货"


# ---------------------------------------------------------------- 成品音轨


def _audio_script():
    return load_script("brand/make_audio_brand.py", "aim_script_make_audio_brand")


def test_the_audio_script_reads_the_shipped_window_file(monkeypatch):
    """脚本必须读已入库的窗口文件，而不是自己挑。

    窗口是**决策**，入库；脚本只负责按那个决定切片、混音。
    """
    monkeypatch.delenv("BRAND_WINDOWS_PATH", raising=False)
    module = _audio_script()
    assert module.WINDOWS == aim_paths.model_dir(SLUG) / "brand_windows.json"


def test_the_audio_script_refuses_to_produce_when_windows_do_not_connect(tmp_path):
    """窗口不相接就拒产——不能让错口径流到成片。"""
    windows = aim_paths.model_dir(SLUG) / "brand_windows.json"
    raw = json.loads(windows.read_text(encoding="utf-8"))
    raw["outro_start_s"] = 31.8
    broken = tmp_path / "brand_windows.json"
    broken.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(BRAND_SCRIPTS / "make_audio_brand.py")],
        check=False, capture_output=True, text=True,
        env={**os.environ, "BRAND_WINDOWS_PATH": str(broken)},
    )
    assert proc.returncode != 0, "窗口不相接时脚本竟然产出了成品"
    assert "不相接" in (proc.stdout + proc.stderr)


def test_fades_stay_short():
    """淡出要短：太长会把刚接上的闭环淡没。"""
    module = _audio_script()
    assert module.FADE_OUT <= 0.1, "片尾淡出过长，会把闭环淡没"
    assert module.FADE_IN_INTRO <= 0.1
    assert module.MIX_FADE_OUT <= 0.1


def test_the_shipped_windows_connect():
    """已入库的窗口必须首尾相接：片尾结束点 == 片头起点。

    这条是**这个人的事实**——窗口文件跟着人走，所以守卫也在这边。
    （另有守卫读的是模型声明的那份窗口文件。）
    """
    windows = aim_paths.model_dir(SLUG) / "brand_windows.json"
    raw = json.loads(windows.read_text(encoding="utf-8"))
    duration = float(raw["duration_s"])
    intro_start = float(raw["intro_start_s"])
    outro_start = float(raw["outro_start_s"])
    assert outro_start + duration == pytest.approx(intro_start, abs=0.01), (
        f"片尾结束在 {outro_start + duration:.3f}s，片头起于 {intro_start:.3f}s——"
        f"没有相接"
    )
