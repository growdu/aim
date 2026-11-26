"""换人回归：**换一个人**必须从头到尾都能跑。

**为什么要有这条。** 「换人只改模型，不改代码」是本仓的规矩，
但这句话很容易**只在文档里成立**：脚本里某个角落还留着上一个人的事实
（眼镜规格、衣服色、背景 prompt），换个人之后生成出来的还是他的东西——
而**画面照样生成、时长照样对**，没有任何报错。这种错最难查：它不崩。

所以这条守卫**换一个人跑一遍**：造一个**跟现在这个人完全不同**的人
（不戴眼镜、没有耳麦、配色不一样、品牌词不一样、背景 prompt 不一样），
把整套流程指过去，断言：

- 事实都跟着模型走（眼镜、配色、背景 prompt）；
- 不戴眼镜的人，**加眼镜流程整体跳过**；
- 铭牌定位用的是**这个人的**衣服色；
- **上一个人的东西一处都不许漏进来**。

**为什么用子进程跑脚本**：脚本在 import 时就把模型读进模块里，
在同一个进程里换模型会撞上 `sys.modules` 里缓存的旧模块——
测出来的是上一个人，而那正是这条守卫要抓的错。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from aimkit import look as look_spec
from aimkit import model as model_mod
from aimkit import paths

AIM_ROOT = paths.AIM_ROOT
SCRIPTS = AIM_ROOT / "scripts"

#: 现在这个人（仓里那位）。断言「旧的东西不许漏进来」时用它的事实。
CURRENT = model_mod.load()


#: 另一个人的全部事实：**跟现在这个人完全不同**。
#:
#: 不戴眼镜、没有耳麦、衣服是墨绿（现在这个人是深藏蓝）、
#: 品牌词不一样、两张背景的 prompt 不一样。
OTHER_PERSON = {
    "schema": 3,
    "person": "slowfox",
    "identity": {
        "name": "慢狐",
        "role": "独立研究者",
        "positioning": "把复杂的东西讲慢一点",
        "audience": "刚入门的学生",
        "taboos": ["不用行话吓人"],
        "series": "慢讲系列",
    },
    "voice": {
        "voice_id": "test_voice",
        "voice_name": "测试音色",
        "pitch": 0,
        "speed": 1.0,
        "emotion": "neutral",
        "measured": {},
        "pronunciation": {},
    },
    "look": "3D 卡通小狐狸，暖橘色皮毛，圆眼、浅色肚皮；"
            "穿墨绿 (#1F4D3C) 工装背心，胸口一枚奶白图标，别一块白色小铭牌",
    "persona": "一位慢慢讲、慢慢想的讲述者。\n- 慢\n- 稳",
    "look_spec": {
        "glasses": {},                 # **不戴眼镜**
        "vest_color": "#1F4D3C",
        "badge_icon_color": "#F2E8D5",
        "badge_text_color": "#20302A",
        "headset": "",                 # **没有耳麦**
    },
    "brand": {
        "name": "慢狐",
        "token": "slowfox",
        "tagline": "慢慢讲",
        "site": "slowfox.example",
        "intro_tagline": "Slow · Down",
        "intro_line": "慢慢讲，{brand}陪你把复杂的东西拆开。",
        "outro_line": "下回见。{site}。",
        "outro_narration": "慢一点也没关系。",
        "outro_subtitle": "慢狐 · 拆开看",
        "outro_title": "下回见",
        "outro_labels": ["订阅", "点赞"],
        "share_suffix": "· 慢慢讲",
        "share_emphasis": "慢慢讲",
        "clips": {"intro": "", "outro": ""},
        "audio": {"intro": "", "outro": ""},
        "windows": "",
        "backgrounds": {
            "intro": "一间暖色调的木质书房，午后阳光从百叶窗的缝隙里斜进来。",
            "outro": "一条黄昏时分的河岸，水面平静，远处是低矮的丘陵。",
        },
        # 底板配色也**跟现在这个人不一样**（那边是深藏蓝 / 浅蓝）。
        "colors": {
            "deep": "#3A2E1F",
            "light": "#F0E6D2",
        },
    },
    "assets": {},
}


def _write_person(tmp_path: Path) -> Path:
    """把另一个人写到临时目录，返回他的 `model.json`。"""
    directory = tmp_path / OTHER_PERSON["person"]
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "model.json"
    target.write_text(
        json.dumps(OTHER_PERSON, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _run(code: str, model_path: Path) -> str:
    """在子进程里跑一段代码，环境变量指着另一个人。"""
    env = {**os.environ, model_mod.MODEL_ENV: str(model_path)}
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(AIM_ROOT), env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"子进程跑挂了：\n{proc.stderr}"
    return proc.stdout


#: 打印另一个人主形象 prompt 的那几行。
_CODE_CHARACTER = """
import sys
sys.path.insert(0, "scripts/character")
import generate_character as g
print("GLASSES=" + g.GLASSES_COLOR)
print("PROMPT=" + g.CHARACTER_PROMPT)
"""

#: 打印另一个人两张背景 prompt 的那几行。
_CODE_BACKGROUNDS = """
import sys
sys.path.insert(0, "scripts/brand")
import generate_backgrounds as b
for which, (prompt, dest) in b._backgrounds().items():
    print(f"{which}={prompt}")
"""

#: 打印品牌片底板用的两个颜色（渲染脚本 import 时就把模型读进去了）。
_CODE_COLOURS = """
import sys
sys.path.insert(0, "scripts/brand")
import render_brand as r
print("DEEP=" + ",".join(f"{c:.4f}" for c in r.DEEP))
print("LIGHT=" + ",".join(f"{c:.4f}" for c in r.LIGHT))
"""

#: 用**另一个人的衣服色**造一张带铭牌的图，看看能不能定位到。
_CODE_BADGE = """
import sys
sys.path.insert(0, "scripts/character")
from PIL import Image
import stamp_badge
from aimkit import look as look_spec
from aimkit import model as model_mod

vest = look_spec.vest_rgb(model_mod.load())
canvas = 1536
image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
head = Image.new("RGBA", (canvas, canvas), (200, 210, 220, 255))
image.paste(head.crop((560, 90, 976, 400)), (560, 90))
body = Image.new("RGBA", (canvas, canvas), tuple(vest) + (255,))
image.paste(body.crop((200, 400, 1336, 900)), (200, 400))
badge = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
for x in range(400, 590):
    for y in range(520, 568):
        badge.putpixel((x, y), (255, 255, 255, 255))
image.paste(badge, (0, 0), badge)
print("BOX=" + str(stamp_badge.find_badge(image)))
"""


# ---- 事实跟着模型走 ------------------------------------------------------


def test_the_facts_come_from_the_other_model(tmp_path):
    """眼镜、耳麦、衣服色、背景 prompt——都读另一个人的模型。"""
    model = model_mod.load(_write_person(tmp_path))

    assert model.person == OTHER_PERSON["person"]
    assert look_spec.has_glasses(model) is False
    assert look_spec.glasses_style(model) == ""
    assert look_spec.glasses_color(model) == ""
    assert look_spec.headset(model) == ""
    assert look_spec.vest_rgb(model) == (0x1F, 0x4D, 0x3C)
    assert model.background_prompt("intro") == \
        OTHER_PERSON["brand"]["backgrounds"]["intro"]
    assert model.background_prompt("outro") == \
        OTHER_PERSON["brand"]["backgrounds"]["outro"]


def test_the_glasses_flow_skips_for_a_person_without_glasses(tmp_path):
    """不戴眼镜的人：加眼镜流程**整体跳过**——不是硬加一副。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "character" / "add_glasses.py")],
        cwd=str(AIM_ROOT),
        env={**os.environ, model_mod.MODEL_ENV: str(_write_person(tmp_path))},
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "不戴眼镜" in proc.stdout, proc.stdout


def test_the_prompts_carry_the_other_person(tmp_path):
    """主形象 prompt 里是**另一个人**的东西，旧的东西一处都不许漏。"""
    out = _run(_CODE_CHARACTER, _write_person(tmp_path))

    assert "狐狸" in out, "另一个人的外观没进 prompt"
    assert "墨绿" in out, "另一个人的衣服没进 prompt"
    assert "眼镜" not in out, "另一个人不戴眼镜，prompt 里却提了眼镜"

    # 现在这个人的事实，一处都不许漏进来
    assert CURRENT.look not in out
    for fact in (CURRENT.look_spec.get("vest_color") or "",
                 CURRENT.look_spec.get("badge_icon_color") or "",
                 (CURRENT.look_spec.get("glasses") or {}).get("style") or "",
                 CURRENT.brand.get("token") or ""):
        if fact:
            assert fact not in out, f"prompt 里漏进了现在这个人的东西：{fact!r}"


def test_the_background_prompts_come_from_the_other_model(tmp_path):
    """背景 prompt 跟着模型走；**框架的规矩**（不许拼接）照样加上。"""
    out = _run(_CODE_BACKGROUNDS, _write_person(tmp_path))

    assert "书房" in out, "另一个人的片头背景 prompt 没进来"
    assert "河岸" in out, "另一个人的片尾背景 prompt 没进来"
    assert "单一连续空间" in out, "框架的规矩（不许拼接）丢了"
    for which in ("intro", "outro"):
        assert OTHER_PERSON["brand"]["backgrounds"][which] in out


def test_the_plate_colours_come_from_the_other_model(tmp_path):
    """品牌片底板的配色跟着模型走。

    以前这两个颜色**写死在渲染脚本里**——换个人，片子还是上一个人的配色。
    """
    out = _run(_CODE_COLOURS, _write_person(tmp_path))

    def as_cairo(hex_value: str) -> str:
        return ",".join(f"{int(hex_value[i:i + 2], 16) / 255:.4f}"
                        for i in (1, 3, 5))

    assert "DEEP=" + as_cairo("#3A2E1F") in out, out
    assert "LIGHT=" + as_cairo("#F0E6D2") in out, out

    # 现在这个人的配色，一点都不许漏进来
    for which in ("deep", "light"):
        current = CURRENT.brand_colour(which)
        if current:
            assert as_cairo(current) not in out, f"底板还带着现在这个人的配色：{current}"


def test_the_badge_is_found_with_the_other_vest_colour(tmp_path):
    """铭牌定位用的是**这个人的衣服色**——换个人也照样找得到。"""
    out = _run(_CODE_BADGE, _write_person(tmp_path))
    assert "BOX=(400, 520, 590, 568)" in out, out


def test_the_doctor_reports_the_other_person(tmp_path):
    """体检认的是**指给它的那个人**。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "doctor.py"),
         str(_write_person(tmp_path))],
        cwd=str(AIM_ROOT), capture_output=True, text=True,
    )
    assert OTHER_PERSON["person"] in proc.stdout, proc.stdout
    # 素材一个都没声明 → 缺东西 → 退出码 1（缺素材不是错误，但要报出来）
    assert proc.returncode == 1, proc.stdout
