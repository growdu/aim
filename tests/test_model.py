"""`model.json` 的形状与读法。

**这份契约错了要报错，不是降级**——所以这些测试盯的都是「报错」。
"""
from __future__ import annotations

import json

import pytest

from aimkit import model as model_mod
from aimkit import paths

FIXTURE = paths.model_path("growdu")


def _write(tmp_path, data, name="model.json"):
    target = tmp_path / name
    target.write_text(
        data if isinstance(data, str) else json.dumps(data, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def _base() -> dict:
    return {
        "schema": 1,
        "person": "growdu",
        "voice": {"voice_id": "Chinese (Mandarin)_Radio_Host"},
    }


# ---- 读得到 -------------------------------------------------------------


def test_it_reads_the_model_from_the_environment(monkeypatch):
    monkeypatch.setenv(model_mod.MODEL_ENV, str(FIXTURE))
    loaded = model_mod.load()
    assert loaded.person == "growdu"
    assert loaded.voice["voice_id"] == "Chinese (Mandarin)_Radio_Host"


def test_the_default_is_the_person_in_the_models_directory(monkeypatch):
    monkeypatch.delenv(model_mod.MODEL_ENV, raising=False)
    assert model_mod.model_file() == FIXTURE


def test_the_relative_paths_resolve_against_the_model_file(monkeypatch):
    monkeypatch.setenv(model_mod.MODEL_ENV, str(FIXTURE))
    loaded = model_mod.load()
    assert loaded.assets["mascot"] == FIXTURE.parent / "assets/character/growdu_character_2k_nobg.png"
    assert loaded.brand_file("windows") == FIXTURE.parent / "brand_windows.json"


def test_an_absolute_path_is_kept_as_it_is(tmp_path):
    absolute = tmp_path / "somewhere" / "mascot.png"
    assert model_mod.resolve(tmp_path, str(absolute)) == absolute


# ---- 读不了 = 硬错误 ----------------------------------------------------


def test_a_missing_model_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv(model_mod.MODEL_ENV, str(tmp_path / "nope.json"))
    with pytest.raises(model_mod.ModelError) as excinfo:
        model_mod.load()
    assert "nope.json" in str(excinfo.value)


def test_a_broken_model_is_an_error(tmp_path, monkeypatch):
    broken = _write(tmp_path, "{ 这不是 JSON")
    monkeypatch.setenv(model_mod.MODEL_ENV, str(broken))
    with pytest.raises(model_mod.ModelError):
        model_mod.load()


def test_an_unknown_schema_is_an_error(tmp_path, monkeypatch):
    data = _base()
    data["schema"] = 99
    target = _write(tmp_path, data)
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))
    with pytest.raises(model_mod.ModelError) as excinfo:
        model_mod.load()
    assert "schema" in str(excinfo.value)


def test_a_missing_voice_id_is_an_error(tmp_path, monkeypatch):
    target = _write(tmp_path, {"schema": 1, "person": "growdu", "voice": {}})
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))
    with pytest.raises(model_mod.ModelError) as excinfo:
        model_mod.load()
    assert "voice.voice_id" in str(excinfo.value)


# ---- 可空的字段 ----------------------------------------------------------


def test_the_identity_may_be_empty(tmp_path, monkeypatch):
    target = _write(tmp_path, {"schema": 1, "person": "growdu", "voice": {"voice_id": "x"}})
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))
    loaded = model_mod.load()
    assert loaded.identity == {}
    assert loaded.persona == ""
    assert loaded.look == ""


def test_the_persona_is_free_text(tmp_path, monkeypatch):
    data = _base()
    data["persona"] = "一段话，随便写。\n- 还能带列表"
    target = _write(tmp_path, data)
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))
    loaded = model_mod.load()
    assert loaded.persona.startswith("一段话")


# ---- 两条硬规矩 ----------------------------------------------------------


def test_the_metadata_carries_no_media_files():
    """元数据里只有路径，没有媒体文件。"""
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for key, value in raw["assets"].items():
        assert isinstance(value, str), f"{key} 只能是路径"
    for kind in ("clips", "audio"):
        for name, value in raw["brand"][kind].items():
            assert isinstance(value, str), f"brand.{kind}.{name} 只能是路径"


def test_the_model_directory_holds_no_media():
    """模型目录里不该出现媒体文件——素材在 `assets/`（不入库）。"""
    media = {".png", ".jpg", ".jpeg", ".mp4", ".wav", ".mp3"}
    for path in FIXTURE.parent.rglob("*"):
        if path.is_file():
            assert path.suffix.lower() not in media, f"模型目录里不该有媒体：{path}"


def test_the_brand_windows_lives_next_to_the_model():
    assert (FIXTURE.parent / "brand_windows.json").exists()
