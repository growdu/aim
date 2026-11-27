"""**命令行入口**要站得住：一条脚本都不能漏，每条都要能叫。

**为什么这是条守卫**：aim 的交付形式是「CLI + skill + agent」——
CLI 那一半就是**仓根的 `./aim`**。
它是个**门面**：命令表指向现有的脚本，参数原样转交、退出码原样传回。

守三件事：

1. **每条带 `__main__` 的脚本都在命令表里**——
   漏登记的脚本就**没人能通过 CLI 叫它**，
   交付形式名义上在、实际上缺一块。
2. **命令表里的每一条都指向真实存在的脚本**——指着空气的命令一跑就炸。
3. **`./aim` 本身会答 `--help`**——门面也得能问。

另加一件（`test_the_entry_point_is_executable`）：
**`./aim` 得真的敲得动**——文件要有可执行位，而且 git 得记成 100755。
文档教人敲的是 `./aim`，不是 `python3 aim`。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from aimkit import cli as cli_mod
from aimkit import model as model_mod
from aimkit import paths

AIM_ROOT = paths.AIM_ROOT
SCRIPTS = AIM_ROOT / "scripts"
AIM_CMD = AIM_ROOT / "aim"

#: 要当入口用的脚本：**带 `__main__` 护栏的那些**。
#:
#: 私有的（`_mcode.py` / `_persona.py`）与被 import 的模块
#: （`pronunciation.py`——它只留替换规则）不算入口。
SCRIPTS_UNDER_TEST = sorted(
    path for path in SCRIPTS.rglob("*.py")
    if '__name__ == "__main__"' in path.read_text(encoding="utf-8")
)

#: 跑脚本时得指一份模型——脚本在 import 时就读它。
ENV = {**os.environ, model_mod.MODEL_ENV: str(paths.model_path("growdu"))}


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(AIM_ROOT), capture_output=True, text=True
    )


@pytest.mark.parametrize("script", SCRIPTS_UNDER_TEST,
                         ids=lambda p: p.name)
def test_the_script_answers_help(script: Path):
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(AIM_ROOT), env=ENV, capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"{script.name} 的 --help 退 {proc.returncode}：\n{proc.stderr}"
    )
    out = proc.stdout.strip()
    assert "usage:" in out, f"{script.name} 的 --help 没给 usage：\n{out}"
    # usage 下面得有话——光一行 usage 等于没交代它是干什么的
    assert len(out.splitlines()) >= 3, (
        f"{script.name} 的 --help 只有 usage，没有说明：\n{out}"
    )


def test_every_entry_script_is_registered():
    """**每条入口脚本都得能在 CLI 里叫到。**"""
    registered = {
        (AIM_ROOT / command.script).resolve()
        for command in cli_mod.COMMANDS
    }
    missing = [
        script.relative_to(AIM_ROOT).as_posix()
        for script in SCRIPTS_UNDER_TEST
        if script.resolve() not in registered
    ]
    assert not missing, f"这些脚本没进命令表，CLI 叫不到：{missing}"


def test_every_registered_command_points_at_a_real_script():
    """**命令表指着空气 = 交付形式是假的。**"""
    missing = [
        command.path for command in cli_mod.COMMANDS
        if not (AIM_ROOT / command.script).is_file()
    ]
    assert not missing, f"命令表指着不存在的脚本：{missing}"


def test_the_command_names_are_unique():
    names = [command.path for command in cli_mod.COMMANDS]
    assert len(names) == len(set(names)), f"命令名重了：{names}"


def test_the_entry_point_answers_help():
    """**门面也得能问。**"""
    assert AIM_CMD.is_file(), f"仓根没有 ./aim：{AIM_CMD}"
    proc = subprocess.run(
        [sys.executable, str(AIM_CMD), "--help"],
        cwd=str(AIM_ROOT), env=ENV, capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"./aim --help 退了 {proc.returncode}：\n{proc.stderr}"
    out = proc.stdout
    assert "usage:" in out.lower() or "用法" in out, f"./aim --help 没给用法：\n{out}"
    # 列出来的命令得跟命令表一样多——少列了就是没真列全
    for command in cli_mod.COMMANDS:
        assert command.path in out, f"用法里少了命令：{command.path}"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows 没有可执行位这一说，也敲不动无扩展名的脚本",
)
def test_the_entry_point_is_executable():
    """**`./aim` 得真的敲得动。**

    文档教的是 `./aim --help`——**不是** `python3 aim --help`。
    文件少了可执行位，照文档走的人第一步就卡在
    `Permission denied`（退 126），而文档一个字都不会提醒他。

    **所以这条守卫不能绕开那一层**：用 `sys.executable` 去调，
    永远能跑——上一条 `test_the_entry_point_answers_help` 验的是
    「模块能被调用」，不是「入口能被敲」，**抓不到这个缺陷**。
    这里要**真的把 `./aim` 执行一遍**。
    """
    assert os.access(AIM_CMD, os.X_OK), (
        f"仓根的 ./aim 没有可执行位——照文档敲会 Permission denied"
        f"（退 126）：{AIM_CMD}\n"
        f"修法：chmod +x aim（git 要记成 100755）"
    )

    try:
        proc = subprocess.run(
            [str(AIM_CMD), "--help"],
            cwd=str(AIM_ROOT), env=ENV, capture_output=True, text=True,
        )
    except OSError as exc:
        pytest.fail(f"直接执行 ./aim 失败了：{exc}")

    assert proc.returncode == 0, (
        f"直接执行 ./aim --help 退了 {proc.returncode}：\n{proc.stderr}"
    )
    assert "用法" in proc.stdout, f"./aim --help 没给用法：\n{proc.stdout}"


def test_the_entry_point_is_tracked_as_executable():
    """**git 得记成 100755。**

    本地 `chmod +x` 是**没用的**——别人 clone 下来还是 644，
    照文档敲还是 Permission denied。**可执行位要跟着提交走。**
    """
    if _git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("不在 git 仓库里，跳过")

    result = _git("ls-files", "--stage", "aim")
    assert result.returncode == 0, f"git 里没有 ./aim：{result.stderr}"

    staged = result.stdout.strip().split()
    assert staged, f"git ls-files 没给出 ./aim 的记录：{result.stdout!r}"
    mode = staged[0]

    assert mode == "100755", (
        f"git 里的 ./aim 是 {mode}，不是 100755——"
        f"别人 clone 下来没有可执行位，照文档敲会 Permission denied\n"
        f"修法：git update-index --chmod=+x aim（并提交这个模式变化）"
    )


@pytest.mark.parametrize("command", cli_mod.COMMANDS, ids=lambda c: c.path)
def test_the_command_forwards_help_to_its_script(command):
    """**参数原样转交**——`aim <命令> --help` 得看到脚本自己的用法。"""
    proc = subprocess.run(
        [sys.executable, str(AIM_CMD), *command.path.split(), "--help"],
        cwd=str(AIM_ROOT), env=ENV, capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"aim {command.path} --help 退了 {proc.returncode}：\n{proc.stderr}"
    )
    assert "usage:" in proc.stdout, (
        f"aim {command.path} --help 没转交出脚本的用法：\n{proc.stdout}"
    )


def test_an_unknown_command_fails_loudly():
    """**不猜**——命令不存在就退非 0，别默默干点什么。"""
    proc = subprocess.run(
        [sys.executable, str(AIM_CMD), "没有这个命令"],
        cwd=str(AIM_ROOT), env=ENV, capture_output=True, text=True,
    )
    assert proc.returncode != 0, "命令不存在却退 0——那是默默吞了"
