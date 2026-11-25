"""声音侧——多音字表从 `model.json` 来，替换规则在这里。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from aimkit import model as model_mod
from aimkit import paths

SCRIPT = paths.SCRIPTS_DIR / "voice" / "pronunciation.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("aim_pronunciation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pronunciation():
    return _load_module()


def test_the_rules_come_from_the_model_not_from_the_source(pronunciation):
    model = model_mod.load()
    assert pronunciation.PRONUNCIATION_SUBSTITUTIONS == model.voice["pronunciation"]


def test_the_model_keeps_the_rules_it_needs():
    rules = model_mod.load().voice["pronunciation"]
    assert "行锁" in rules
    assert "一行" in rules


def test_a_standalone_yi_hang_is_replaced(pronunciation):
    assert pronunciation.apply_substitutions("一行数据") == "壹行数据"


def test_a_yi_hang_inside_a_phrase_is_not_replaced(pronunciation):
    assert pronunciation.apply_substitutions("每一行数据") == "每一行数据"


def test_an_ambiguous_word_is_replaced(pronunciation):
    assert pronunciation.apply_substitutions("行锁") == "航锁"


def test_the_rules_can_be_passed_in(pronunciation):
    assert pronunciation.apply_substitutions("一行", {"一行": "壹行"}) == "壹行"
    assert pronunciation.apply_substitutions("一行", {}) == "一行"


def test_the_unverified_words_are_reported(pronunciation):
    """没被任何读音记录覆盖的「行」字词——必须先实测再入库。"""
    assert "行锁" not in pronunciation.unverified_hang_words("行锁")
    assert "行囊" in pronunciation.unverified_hang_words("行囊")


def test_the_pronunciation_judgement_constants_are_consistent():
    """判据本身的常量不能自相矛盾——阈值漂了就等于没判。

    判据脚本（`scripts/voice/check_pronunciation.py`）是**这个人的尺子**，
    所以它跟人走，守卫也在这边。
    """
    from _scripts import load_script

    module = load_script("voice/check_pronunciation.py",
                         "aim_script_check_pronunciation")
    assert module.GAMMA_RATIO_MIN >= 20, "摩擦比门槛太低，浊音段会被当成摩擦噪声"
    assert module.GAMMA_CENTROID_MIN >= 3500, \
        "谱心门槛低于 [ɕ] 的实测下沿（4419 Hz）"
    assert module.ONSET_WINDOW <= 0.10, (
        "词首窗口大于 100 ms 就会扫到后一个字（实测「锁」的 /s/ 在 +126 ms 以后）"
    )
