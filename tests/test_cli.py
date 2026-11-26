"""每条脚本都要**会答 `--help`**。

**为什么这是条守卫**：aim 的交付形式是「一个仓 + 一组命令行脚本」——
没有可安装的包、没有 agent、没有二进制。所以**唯一的入口就是命令行**。
一条脚本把 `--help` 当成文件名（于是答「文件不存在，跳过」），
用的人就得先读源码才知道它要什么——交付形式当场就说不清了。

所以这里守两件事：

1. **每条脚本 `--help` 都退 0**（不是把 `--help` 当路径，不是抛栈）；
2. **答出来的 usage 里说得清它是干什么的**（有 description，不是一行 usage）。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from aimkit import model as model_mod
from aimkit import paths

AIM_ROOT = paths.AIM_ROOT
SCRIPTS = AIM_ROOT / "scripts"

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
