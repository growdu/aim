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
        "schema": 3,
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


def test_several_people_are_never_guessed(tmp_path, monkeypatch):
    """仓里有好几个人时**绝不猜**——猜错就是拿别人的事实去生成。

    以前这里是写死一个人（`DEFAULT_SLUG`）：仓里多了一个人，脚本照样
    拿那个人的事实去生成另一个人的素材与片子——**画面照样生成、
    时长照样对**，没有任何报错。
    """
    people = tmp_path / "models"
    for slug in ("alice", "bob"):
        (people / slug).mkdir(parents=True)
        (people / slug / "model.json").write_text("{}", encoding="utf-8")
    monkeypatch.delenv(model_mod.MODEL_ENV, raising=False)
    monkeypatch.setattr(model_mod.paths, "MODELS_DIR", people)

    with pytest.raises(model_mod.ModelError) as excinfo:
        model_mod.model_file()
    message = str(excinfo.value)
    assert "alice" in message and "bob" in message, message


def test_no_people_at_all_is_an_error(tmp_path, monkeypatch):
    """一个人都没有时也要报错——别返回一个空模型。"""
    monkeypatch.delenv(model_mod.MODEL_ENV, raising=False)
    monkeypatch.setattr(model_mod.paths, "MODELS_DIR", tmp_path / "empty")
    with pytest.raises(model_mod.ModelError):
        model_mod.model_file()


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
    target = _write(tmp_path, {"schema": 3, "person": "growdu", "voice": {}})
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))
    with pytest.raises(model_mod.ModelError) as excinfo:
        model_mod.load()
    assert "voice.voice_id" in str(excinfo.value)


def test_an_old_schema_is_an_error(tmp_path, monkeypatch):
    """旧形状读不出这个人的眼镜规格与背景 prompt——**报错退出**，不降级。

    降级更糟：脚本会拿着**上一个形状**的事实去生成，
    生成出来的还是上一个人的样子，而画面照样生成、时长照样对。
    """
    data = _base()
    data["schema"] = model_mod.SCHEMA_VERSION - 1
    target = _write(tmp_path, data)
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))
    with pytest.raises(model_mod.ModelError) as excinfo:
        model_mod.load()
    assert "schema" in str(excinfo.value)


def test_a_colour_that_is_not_a_colour_is_an_error(tmp_path, monkeypatch):
    """颜色一律 `#RRGGBB`——颜色要喂给 cairo 与 numpy，
    写成 `rgb(...)` 或漏了 `#` 都会在渲染那一刻才炸。"""
    data = _base()
    data["look_spec"] = {"vest_color": "rgb(43,76,126)"}
    target = _write(tmp_path, data)
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))
    with pytest.raises(model_mod.ModelError) as excinfo:
        model_mod.load()
    assert "#RRGGBB" in str(excinfo.value)


def test_the_brand_colour_is_read_from_the_model(tmp_path, monkeypatch):
    """品牌片底板的配色是**这个人的事实**，从模型读。"""
    data = _base()
    data["brand"] = {"colors": {"deep": "#123456", "light": "#ABCDEF"}}
    target = _write(tmp_path, data)
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))
    loaded = model_mod.load()
    assert loaded.brand_colour("deep") == "#123456"
    assert loaded.brand_colour("light") == "#ABCDEF"


def test_the_brand_colour_may_be_empty(tmp_path, monkeypatch):
    """没声明底板配色**不是错误**——空 = 还没定，渲染退回中性色。"""
    target = _write(tmp_path, _base())
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))
    loaded = model_mod.load()
    assert loaded.brand_colour("deep") == ""
    assert loaded.brand_colour("light") == ""


def test_a_bad_brand_colour_is_an_error(tmp_path, monkeypatch):
    """颜色写成「深蓝」这种文字——渲染那一刻才炸，所以要在契约里挡住。"""
    data = _base()
    data["brand"] = {"colors": {"deep": "深蓝"}}
    target = _write(tmp_path, data)
    monkeypatch.setenv(model_mod.MODEL_ENV, str(target))
    with pytest.raises(model_mod.ModelError) as excinfo:
        model_mod.load()
    assert "#RRGGBB" in str(excinfo.value)


# ---- 可空的字段 ----------------------------------------------------------


def test_the_identity_may_be_empty(tmp_path, monkeypatch):
    target = _write(tmp_path, {"schema": 3, "person": "growdu", "voice": {"voice_id": "x"}})
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
