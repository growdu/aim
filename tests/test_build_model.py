"""`build_model.py`——把散在各处的**确认结论**收成一份 JSON。

**它不生成任何东西**：不生成形象、不合成音频。
它只做三件事：归一化、校验、写出。

**最要紧的一条是「不编」**：身份类的东西（站名、定位、受众）只能人写。
脚本把没写的留成空（空 = 「还没定」），**不拿占位符糊过去**——
糊过去了，下游就分不清「定错了」和「还没定」。
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from aimkit import model as model_mod
from aimkit import paths

from _scripts import load_script


def _build_model():
    return load_script("build_model.py", "aim_script_build_model")


def _write(path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")


#: 事先输入的确认结论——**跟仓里那个人完全不同的一个人**。
#:
#: 之所以不用仓里那个人：两边值一样的话，「原样保留」可能只是**撞对了**。
#: **换一个人**，保留与丢失才分得清。
#:
#: 这份草稿是**完整的**：每一段都写全了，所以归一化**没东西可补**——
#: 写出来的那份 model 应该跟这份草稿**逐字一致**。
DRAFT: dict = {
    "person": "yunque",
    "identity": {
        "name": "云雀",
        "role": "独立开发者",
        "positioning": "把复杂的事讲得让人睡得着",
        "audience": "刚接触分布式系统的后端工程师",
        "taboos": ["不用术语吓人"],
        "series": "睡前十分钟系列",
    },
    "voice": {
        "voice_id": "Chinese (Mandarin)_Warm_Narrator",
        "voice_name": "温和讲述者",
        "pitch": -2,
        "speed": 0.95,
        "emotion": "calm",
        "measured": {"f0_median": 103.2, "chars_per_sec": 3.9},
        "pronunciation": {"一行": "壹行"},
    },
    "look": "3D 卡通小鸟，浅灰蓝羽毛，短喙；穿米白 (#F0EAD8) 工装外套，"
            "胸口一枚砖红图标，别一块白色小铭牌",
    "persona": "一位不着急的讲述者。\n- 不着急\n- 讲得清楚\n- 不吓人",
    "look_spec": {
        "glasses": {"style": "圆框", "color": "#6B4E3D"},
        "vest_color": "#F0EAD8",
        "badge_icon_color": "#B5442F",
        "badge_text_color": "#3A3128",
        "headset": "无",
    },
    "brand": {
        "name": "云雀",
        "token": "yunque",
        "tagline": "讲得慢，听得懂",
        "site": "yunque.example",
        "intro_tagline": "Slow · Clear",
        "intro_line": "{brand}，陪你把复杂的事拆开看。",
        "outro_line": "下回见。{site}。",
        "outro_narration": "睡个好觉。",
        "outro_subtitle": "云雀 · 拆开看",
        "outro_title": "下回见",
        "outro_labels": ["订阅", "点赞"],
        "share_suffix": "· 讲得慢",
        "share_emphasis": "讲得慢",
        "clips": {"intro": "assets/brand/clips/yunque_intro.mp4", "outro": ""},
        "audio": {"intro": "", "outro": ""},
        "windows": "brand_windows.json",
        "backgrounds": {
            "intro": "一间暖色调的木质书房，午后阳光斜进来。",
            "outro": "一条黄昏时分的河岸，水面平静。",
        },
        "colors": {"deep": "#3A2E1F", "light": "#F0E6D2"},
    },
    "assets": {
        "source": "assets/character/yunque.jpeg",
        "mascot": "assets/character/yunque_mascot.png",
        "avatar": "",
    },
}


def test_the_core_flow_turns_a_draft_into_the_matching_model(tmp_path):
    """**核心功能**：事先输入的人格等信息 → 生成对应的 model。

    这条走的是**完整的路**：`./aim model build`（CLI 门面 → 命令表 →
    脚本）→ 写出的 model.json → 读回来（`aimkit.model.load`）。
    也就是**照着文档敲的那条路**，不是把脚本当函数调用。

    断言的是**写出来的那份是不是这个人**：人格、身份、音色、形象、
    形象规格、品牌词、两张背景的 prompt、底板配色、素材路径——
    **一一对上**。别的地方都在拆着验（不编、坏形状不写、空壳补齐），
    这里验的是**合起来**：整条路走通，出来的是同一个人。
    """
    source = tmp_path / "draft.json"
    _write(source, DRAFT)
    out = tmp_path / DRAFT["person"] / "model.json"

    proc = subprocess.run(
        [sys.executable, str(paths.AIM_ROOT / "aim"), "model", "build",
         "--person", DRAFT["person"], "--from", str(source), "--out", str(out)],
        cwd=str(paths.AIM_ROOT), capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"aim model build 退了 {proc.returncode}：\n{proc.stderr}"
    )
    assert out.is_file(), f"没写出 model.json：{out}"
    assert "人格" in proc.stdout, f"没说清楚人格定了：\n{proc.stdout}"

    data = json.loads(out.read_text(encoding="utf-8"))

    # 形状：版本号与标识由脚本统一
    assert data["schema"] == model_mod.SCHEMA_VERSION
    assert data["person"] == DRAFT["person"]

    # **事先输入的，一样不落**
    assert data["persona"] == DRAFT["persona"]
    assert data["identity"] == DRAFT["identity"]
    assert data["voice"] == DRAFT["voice"]
    assert data["look"] == DRAFT["look"]
    assert data["look_spec"] == DRAFT["look_spec"]
    assert data["brand"] == DRAFT["brand"]
    assert data["assets"] == DRAFT["assets"]

    # 读回来——访问器给出的也是这个人
    model = model_mod.load(out)
    assert model.person == DRAFT["person"]
    assert model.persona == DRAFT["persona"]
    assert model.identity["name"] == DRAFT["identity"]["name"]
    assert model.voice["voice_id"] == DRAFT["voice"]["voice_id"]
    assert model.background_prompt("intro") == \
        DRAFT["brand"]["backgrounds"]["intro"]
    assert model.background_prompt("outro") == \
        DRAFT["brand"]["backgrounds"]["outro"]
    assert model.brand_colour("deep") == DRAFT["brand"]["colors"]["deep"]
    assert model.brand_colour("light") == DRAFT["brand"]["colors"]["light"]

    # **相对路径的基准是 model.json 所在目录**——下游不用知道仓根在哪
    assert model.asset("mascot") == \
        out.parent / "assets/character/yunque_mascot.png"
    assert model.brand_file("clips", "intro") == \
        out.parent / "assets/brand/clips/yunque_intro.mp4"
    assert model.brand_file("windows") == out.parent / "brand_windows.json"
    # 空 = 还没定，不是错误
    assert model.asset("avatar") is None


def test_it_keeps_the_existing_values(tmp_path):
    """已有的值原样保留。"""
    script = _build_model()
    source = tmp_path / "draft.json"
    _write(source, {
        "schema": 3,
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
        "schema": 3,
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
        "schema": 3,
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
    _write(source, {"schema": 3, "person": "growdu", "voice": {}})
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
        "schema": 3,
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
        "schema": 3,
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
        "schema": 3,
        "person": "growdu",
        "voice": {"voice_id": "v"},
    })
    out = tmp_path / "model.json"

    assert script.main(["--person", "growdu", "--from", str(source),
                        "--out", str(out)]) == 0

    data = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(data[field], dict)
