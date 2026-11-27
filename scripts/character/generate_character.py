#!/usr/bin/env python3
"""生成角色形象。

素材源：模型里声明的原型参考图（`model.json` 的 `assets.source`）——**使用者的素材**。
角色外观取 `model.json` 的 `look`，文件名前缀取 `person`。
产出（`<slug>` 是 `person`）：
  models/<slug>/assets/character/<slug>_character_2k.png       主形象（白底）
  models/<slug>/assets/character/<slug>_character_2k_nobg.png  透明底版（合成进视频用）
  character/<slug>_pose_sheet.png          6 姿态设定表

依赖 mcode-tools CLI（mcode-tools-master skill）：
  mcode-tools upload_temp_url <file>              # 本地图片 → 临时 URL
  mcode-tools connector call connector__matrix__generate_image --args-file <json>
  mcode-tools connector call connector__matrix__remove_image_background --args <json>
  mcode-tools get_asset_url <node_id>             # node_id → 下载 URL

用法：
  python3 scripts/generate_character.py

注意：
  - 每次生成都会消耗生成额度，重复运行前先确认是否真的需要重做。
  - 铭牌必须显示品牌词（`model.json` 的 `brand.token`，品牌标识），但**文字不能由模型生成**：
    模型的中英文会乱码。生成后统一跑一遍 stamp_badge.py，
    把铭牌刷成纯白再用真实字体写上品牌词。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mcode import call, download, upload  # noqa: E402  同目录脚本
from _persona import persona_prompt  # noqa: E402  人格气质唯一来源
from stamp_badge import stamp_badge  # noqa: E402  同目录脚本

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))          # aim 仓根
from aimkit import look as look_spec  # noqa: E402  形象规格唯一来源
from aimkit import model as model_mod  # noqa: E402
from aimkit import paths as aim_paths  # noqa: E402

_MODEL = model_mod.load()
SLUG = _MODEL.person
LOOK = _MODEL.look or "3D 卡通风格的拟人化角色"
BRAND_NAME = _MODEL.brand.get("name", "")
# 身份层：**空就是空**，不编。
#
# 以前这里给 `role` / `positioning` 都备了一个兜底文案——
# 那是**替这个人编身份**：模型里没写，脚本就悄悄塞一个进去，
# 生成出来的形象带着别人（或者根本不存在的人）的人设。
ROLE = (_MODEL.identity.get("role") or "").strip()
POSITIONING = (_MODEL.identity.get("positioning") or "").strip()

# 眼镜：**这个人的事实**，从 `look_spec.glasses` 读。没声明 = 不戴眼镜。
GLASSES_COLOR = look_spec.glasses_color(_MODEL)
GLASSES_STYLE = look_spec.glasses_style(_MODEL)
HAS_GLASSES = look_spec.has_glasses(_MODEL)

CHAR_DIR = aim_paths.character_dir(SLUG)
# 这个人的素材根（`aim/models/<slug>/assets/`）
PERSON_ROOT = aim_paths.person_assets_dir(SLUG)

# 形象原型参考图：使用者的素材，路径写在模型里。**没配 = 不跑这个脚本。**
SOURCE_IMAGE = _MODEL.asset("source")


def _identity_sentence() -> str:
    """身份那一句——**只写模型里有的**。

    `role` / `positioning` 没写就只写通用的一句，**不拿占位符糊过去**。
    """
    bits: list[str] = []
    if ROLE:
        bits.append(f"定位是「{ROLE}」")
    if POSITIONING:
        bits.append(f"人设是「{POSITIONING}」")
    tail = ("，" + "、".join(bits)) if bits else ""
    return f"角色设定：一位拟人化角色「{BRAND_NAME}」{tail}。"


def _look_bullets() -> str:
    """「按形象设定补齐」的那几条——**逐条来自模型**。

    外观散文来自 `look`，耳麦来自 `look_spec.headset`。
    """
    return look_spec.appearance_prompt(_MODEL, include_glasses=False)

if HAS_GLASSES:
    GLASSES_PROMPT = f"""眼镜（必须戴）：
- 戴一副{GLASSES_STYLE}眼镜，镜框颜色 {GLASSES_COLOR}，框条纤细规整，镜片带极小圆角
- 镜片完全透明，能清楚看到眼睛，不要镜片反光、不要镜片变色、不要墨镜遮眼
- 眼镜架在两只眼睛上，佩戴位置与角度自然，镜框总宽度与两只大眼睛的总跨度相称
- 镜腿从镜框两侧水平伸向两只耳朵"""
else:
    # 没声明眼镜 = 这个人不戴眼镜。**prompt 里一个字都不提**——
    # 提了就是给这个人硬加一副眼镜。
    GLASSES_PROMPT = ""

#: 设定表那一段的眼镜提醒（只有戴眼镜的人有）。
GLASSES_POSE_LINE = (
    "- 六个姿态里的角色全都戴着这副眼镜，佩戴位置与角度各自自然\n"
    if HAS_GLASSES else ""
)

CHARACTER_PROMPT = f"""以图1（{LOOK}，坐姿形象）为主体原型，生成一张专业的产品级角色设定图（character turnaround sheet）。

{_identity_sentence()}

{persona_prompt()}

必须保留图1的视觉特征：
- 图1里的全部外观特征（皮肤质感、配色、五官、配饰）一字不改
- 整体为正面坐姿、白色纯净背景
- 柔和均匀的棚拍打光，无强反光

形象按下面这些设定补齐（图1 里没有的部分）：
{_look_bullets()}
- 胸前别一块白色小铭牌（保持空白纯白）

{GLASSES_PROMPT}

画面要求：
- 纯白背景 (#FFFFFF)，无投影或极淡的接触阴影
- 主体居中，留出充足白边，适合后续做二次合成与局部抠图
- 造型干净、克制，不要拟人化过度（不要人类表情、不要多余肢体）
- 右侧留一小块空白区域用于后续叠加文字

风格：干净的 3D 卡通渲染，产品级质感，类似现代科技品牌的吉祥物设计。"""

POSE_PROMPT = f"""以图1（{LOOK}）为唯一原型，生成一张角色姿态设定表。

IMPORTANT — 铭牌上绝对不要有任何文字：胸口那块白色矩形铭牌必须是完全空白的纯白色，没有任何字母、汉字、符号、条纹或任何类似文字的痕迹。

{persona_prompt()}

排版：3 列 × 2 行网格，共 6 个姿态，均匀排列在纯白背景 (#FFFFFF) 上，每个姿态之间有清晰的白色间隔，风格与光完全一致。

六个姿态依次为：
1. 正面坐姿微笑、双手放在身前（中性/默认姿态）
2. 右臂抬起指向右方，示意为正在讲解某个技术概念
3. 右手抬到下巴处作思考状，微微侧头
4. 双手举起做出「数字 2」的手势
5. 正面坐姿但头微微低，看向下方（沉思/讲解细节）
6. 身体略微后仰、双手摊开，表情豁达（收束/总结姿态）

{_look_bullets()}
- 胸前别一块白色小铭牌（保持空白纯白）

{GLASSES_PROMPT}
{GLASSES_POSE_LINE}

硬性要求：
- 严格保持图1的角色设定不变：同一个角色、外观与配色一字不改
- 每个姿态的胸口都别着一块横向长方形的**白色小铭牌**（与图1同款）
- 铭牌严格空白纯白，无任何文字或类似文字的图案
- 六个姿态是同一个角色的不同动作，不是不同的角色；体型比例、颜色、光照完全统一
- 纯白背景，无投影，无场景道具
- 不要任何文字标签、边框、说明文字、字母或数字
- 干净的产品级 3D 卡通渲染质感"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=("从形象原型重新生成主形象与 6 姿态表。"
                     "**会消耗生成额度**——prompt 全部从 model.json 读。"))
    parser.add_argument("--print-prompt", action="store_true",
                        help="只打印 prompt，不生成（不消耗额度）")
    args = parser.parse_args(argv)

    if args.print_prompt:
        print(CHARACTER_PROMPT)
        print("\n" + "-" * 60 + "\n")
        print(POSE_PROMPT)
        return 0

    if SOURCE_IMAGE is None or not SOURCE_IMAGE.exists():
        print(
            "缺少形象原型参考图：在 model.json 的 assets.source 里写上"
            "（留空 = 不跑生成流程，直接用 assets.mascot 指的那张）",
            file=sys.stderr,
        )
        return 1
    CHAR_DIR.mkdir(parents=True, exist_ok=True)
    ref = upload(SOURCE_IMAGE)
    print(f"已上传形象原型：{SOURCE_IMAGE.name}")

    print("生成主形象（白底）…")
    res = call("connector__matrix__generate_image", {"requests": [{
        "prompt": CHARACTER_PROMPT,
        "reference_images": [{"url": ref, "mime_type": "image/jpeg"}],
        "aspect_ratio": "1:1", "area": "2K", "output_format": "png",
        "output_file": f"{SLUG}_character_2k.png", "n": 1,
    }]})
    node = res["success_items"][0]["node_id"]
    main_png = CHAR_DIR / f"{SLUG}_character_2k.png"
    download(node, main_png)
    print(f"  → {main_png.relative_to(PERSON_ROOT)}")

    print("抠透明底…")
    res = call("connector__matrix__remove_image_background", {"image_url": upload(main_png)})
    download(res["node_id"], CHAR_DIR / f"{SLUG}_character_2k_nobg.png")
    print(f"  → {(CHAR_DIR / f'{SLUG}_character_2k_nobg.png').relative_to(PERSON_ROOT)}")

    print("生成 6 姿态设定表…")
    res = call("connector__matrix__generate_image", {"requests": [{
        "prompt": POSE_PROMPT,
        "reference_images": [{"url": upload(main_png), "mime_type": "image/png"}],
        "aspect_ratio": "16:9", "area": "2K", "output_format": "png",
        "output_file": f"{SLUG}_pose_sheet.png", "n": 1,
    }]})
    download(res["success_items"][0]["node_id"], CHAR_DIR / f"{SLUG}_pose_sheet.png")
    print(f"  → {(CHAR_DIR / f'{SLUG}_pose_sheet.png').relative_to(PERSON_ROOT)}")

    print("给铭牌印上品牌词（真实字体渲染）…")
    missing = []
    for target in (main_png, CHAR_DIR / f"{SLUG}_character_2k_nobg.png"):
        if stamp_badge(target) is None:
            missing.append(target)
    if missing:
        # **不许一声不吭地跳过**：铭牌上必须有品牌词，这是硬要求。
        # 盖不上就是模型这批没在胸口画那块白色铭牌——把这一步重做就好。
        print("模型这批没在胸口画白色铭牌，盖不上品牌词："
              + "、".join(p.name for p in missing), file=sys.stderr)
        print("把这一步重做：./aim assets build --from \"character generate\"",
              file=sys.stderr)
        return 1

    print("完成。规范见 specs/形象规范.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
