"""`build_model.py`——把散在各处的**确认结论**收成一份 JSON。

**它不生成任何东西**：不生成形象、不合成音频。
它只做三件事：归一化、校验、写出。

**最要紧的一条是「不编」**：身份类的东西（站名、定位、受众）只能人写。
脚本把没写的留成空（空 = 「还没定」），**不拿占位符糊过去**——
糊过去了，下游就分不清「定错了」和「还没定」。
"""
from __future__ import annotations

import json

import pytest

from aimkit import model as model_mod

from _scripts import load_script


def _build_model():
    return load_script("build_model.py", "aim_script_build_model")


def _write(path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def test_it_keeps_the_existing_values(tmp_path):
    """已有的值原样保留。"""
    script = _build_model()
    source = tmp_path / "draft.json"
    _write(source, {
        "schema": 1,
        "person": "growdu",
        "voice": {"voice_id": "Chinese (Mandarin)_Radio_Host"},
        "look": "一只小象",
    })
    out = tmp_path / "model.json"

    assert script.main(["--person", "growdu", "--from", str(source),
                        "--out", str(out)]) == 0

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["voice"]["voice_id"] == "Chinese (Mandarin)_Radio_Host"
    assert data["look"] == "一只小象"


def test_it_does_not_invent_identity_values(tmp_path):
    """**没写的身份字段就留空**——不拿占位符糊过去。"""
    script = _build_model()
    source = tmp_path / "draft.json"
    _write(source, {
        "schema": 1,
        "person": "growdu",
        "voice": {"voice_id": "v"},
        "identity": {"taboos": []},
    })
    out = tmp_path / "model.json"

    assert script.main(["--person", "growdu", "--from", str(source),
                        "--out", str(out)]) == 0

    identity = json.loads(out.read_text(encoding="utf-8"))["identity"]
    assert identity["taboos"] == []
    for key in ("name", "role", "positioning", "audience", "series"):
        assert identity[key] == "", f"{key} 不该被脚本编出来"


def test_it_fails_when_the_draft_is_another_person(tmp_path, capsys):
    """草稿里写着另一个人 → **不写**。

    静默改名会把一个人的事实写到别人名下——那比写不出来糟得多。
    """
    script = _build_model()
    source = tmp_path / "draft.json"
    _write(source, {
        "schema": 1,
        "person": "alice",
        "voice": {"voice_id": "v"},
    })
    out = tmp_path / "model.json"

    assert script.main(["--person", "growdu", "--from", str(source),
                        "--out", str(out)]) == 1
    assert not out.exists(), "写着别人却写出了文件"

    err = capsys.readouterr().err
    assert "alice" in err and "growdu" in err


def test_it_refuses_to_write_without_a_voice_id(tmp_path, capsys):
    """音色 id 是必填项——缺了就是契约坏了，不是「还没定」。"""
    script = _build_model()
    source = tmp_path / "draft.json"
    _write(source, {"schema": 1, "person": "growdu", "voice": {}})
    out = tmp_path / "model.json"

    assert script.main(["--person", "growdu", "--from", str(source),
                        "--out", str(out)]) == 1
    assert not out.exists()
    assert "voice" in capsys.readouterr().err


def test_the_written_file_passes_validate(tmp_path):
    """写出去的那份，`aimkit.model.load` 读得回来。"""
    script = _build_model()
    source = tmp_path / "draft.json"
    _write(source, {
        "schema": 1,
        "person": "growdu",
        "voice": {"voice_id": "v"},
        "persona": "一段人格。",
    })
    out = tmp_path / "model.json"

    assert script.main(["--person", "growdu", "--from", str(source),
                        "--out", str(out)]) == 0

    model = model_mod.load(out)
    assert model.person == "growdu"
    assert model.persona == "一段人格。"


def test_the_check_mode_writes_nothing(tmp_path):
    """`--check` 只校验，不写。"""
    script = _build_model()
    source = tmp_path / "draft.json"
    _write(source, {
        "schema": 1,
        "person": "growdu",
        "voice": {"voice_id": "v"},
    })
    out = tmp_path / "model.json"

    assert script.main(["--person", "growdu", "--from", str(source),
                        "--out", str(out), "--check"]) == 0
    assert not out.exists()


@pytest.mark.parametrize("field", ["identity", "voice", "brand"])
def test_the_empty_shells_are_filled_in(tmp_path, field):
    """缺的那一段会被补成空壳——**形状**齐了，**值**还是空。"""
    script = _build_model()
    source = tmp_path / "draft.json"
    _write(source, {
        "schema": 1,
        "person": "growdu",
        "voice": {"voice_id": "v"},
    })
    out = tmp_path / "model.json"

    assert script.main(["--person", "growdu", "--from", str(source),
                        "--out", str(out)]) == 0

    data = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(data[field], dict)
