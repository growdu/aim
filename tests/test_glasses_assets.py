"""本机素材的**像素验收**：脸上确实戴着那副深藏蓝方框眼镜。

不是看 prompt，是看像素：脸的区域里得有深藏蓝的方框眼镜。

素材是**用户自带**的（不入库），所以素材不在本机时**跳过**，不是红。
"""
from __future__ import annotations

import numpy as np
import pytest

from aimkit import look
from aimkit import model as model_mod
from aimkit import paths as aim_paths


_MODEL = model_mod.load()
SLUG = _MODEL.person

#: 镜框色**从模型来**：`look_spec.glasses.color`——
#: 换个人换颜色，这里不用改。
FRAME_RGB = look.hex_to_rgb(
    ((_MODEL.look_spec.get("glasses") or {}).get("color") or ""))

#: **色度**容差：颜色归一化后的比例差在它之内，就算镜框色。
#:
#: **为什么比色度，不比绝对通道值。** 渲染的明暗渐变、高光、阴影
#: **不改变色度**，但**绝对通道值**量到的是打光。实测同一副眼镜的三次渲染：
#:
#: | 判据 | 主形象 | 点赞姿态 | 挥手姿态 |
#: | --- | --- | --- | --- |
#: | 绝对通道（老判据） | 4.29% | **0.39%** | 3.14% |
#: | 色度（现在） | 2.35% | 2.09% | 2.23% |
#:
#: 同一副眼镜被量成差 11 倍的两个数——打光把镜框洗淡一点，
#: 老判据就把**真眼镜判成没戴**（实测点赞姿态就是这么红的）。
#: 色度判据差 1.1 倍，量的是**颜色**不是光。
CHROMA_TOL = 0.18

#: 眼镜判据的两个数（**实测标定**，不是拍脑袋）：
#:
#: · **列跨度**：脸区里镜框色像素的最左列到最右列，占主体宽的比例。
#:   实测三张素材：主形象 63.7%、点赞姿态 60.4%、挥手姿态 60.7%。
#:   40% 是安全门槛——它卡在「有眼镜」（≥60%）与「没有眼镜」之间：
#:   实测抹掉镜框后跨度塌到 0；只留两只眼睛（虹膜也是蓝的）时是 27%~29%。
#:
#: · **像素占比**：脸区里镜框色像素占脸区面积的比。实测 2.09% ~ 2.35%，
#:   0.5% 是安全门槛——它保证镜框**有厚度**，不是一根线。
MIN_FRAME_SPAN_RATIO = 0.40
MIN_FRAME_AREA_RATIO = 0.005


def _subject_box(rgb: np.ndarray, alpha: np.ndarray | None):
    """主体包围盒（透明底按 alpha；白底按「不是白」）。"""
    if alpha is not None and alpha.min() < 250:
        mask = alpha > 8
    else:
        mask = ~((rgb[..., 0] > 245) & (rgb[..., 1] > 245) & (rgb[..., 2] > 245))
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def _frame(rgb: np.ndarray) -> np.ndarray:
    """镜框色的像素——按**色度**判。

    角色的**虹膜也是蓝色**、耳朵内壁与阴影是蓝灰色，所以判据要卡得准：
    只按「暗 + 偏蓝」去筛，虹膜和阴影会混进来。按**色度**（归一化后的
    通道比例）去筛就没这个问题——镜框的色度与虹膜、皮肤差得开，
    而明暗打光改不动色度。
    """
    m = np.maximum(rgb.max(axis=2), 1).astype(np.float64)
    chroma = rgb.astype(np.float64) / m[..., None]
    target = np.array(FRAME_RGB, dtype=np.float64)
    target = target / target.max()
    return np.max(np.abs(chroma - target), axis=2) <= CHROMA_TOL


def _face_band(box, height: int):
    """脸所在的那一段行：主体上部 18% ~ 42%。

    眼镜在眼睛上；这个区间的上方是头顶呆毛，下方是耳机与马甲。
    """
    x0, y0, x1, y1 = box
    subject_h = y1 - y0
    return int(y0 + subject_h * 0.18), int(y0 + subject_h * 0.42)


def _glasses_measure(rgb: np.ndarray, alpha: np.ndarray | None):
    """量脸区里的镜框色：返回 (列跨度, 像素数, 脸区面积, 主体宽)。

    **为什么用「列跨度」而不是「最长水平段」。** 早先的判据是「镜框是
    横着走的长条」，量的是**最长水平连续段**。那只在头是正的时候成立：
    点赞姿态的角色头是歪的，镜框上沿是**斜线**，任何一行都截不出长段
    （实测只有主体宽的 2.8%，远低于门槛 6%）——可那张图的眼镜明明在。

    那是**判据的局限，不是素材的毛病**。列跨度对倾斜免疫：镜框横跨两只
    眼睛，不管上沿是平是斜，占的列都是同一段。
    """
    box = _subject_box(rgb, alpha)
    if box is None:
        return 0, 0, 0, 0
    x0, y0, x1, y1 = box
    subject_h = y1 - y0
    subject_w = x1 - x0
    top, bottom = _face_band(box, subject_h)
    band = _frame(rgb)[top:bottom]
    columns = np.flatnonzero(band.any(axis=0))
    span = int(columns[-1] - columns[0] + 1) if columns.size else 0
    return span, int(band.sum()), int(band.size), subject_w


@pytest.mark.parametrize("relative", [
    "character/{slug}_character_2k_nobg.png",
    "brand/{slug}_pose_thumbsup_nobg.png",
    "brand/{slug}_pose_wave_nobg.png",
])
def test_real_assets_wear_navy_square_glasses(relative):
    """本机素材：角色脸上得有那副方框眼镜。

    判据是脸区里的**镜框色掩膜**（色度取自 `look_spec.glasses.color`）：
    - **列跨度**要够宽——镜框横跨两只眼睛（实测 60%~64% 主体宽）；
    - **像素占比**要够多——镜框有厚度，不是一根线。

    眉毛不进这道掩膜（深棕，色度差得开），耳机也不进（纯黑，色度差为 0），
    所以脸区里的镜框色就是镜框本身。
    """
    from PIL import Image

    path = aim_paths.person_assets_dir(SLUG) / relative.format(slug=SLUG)
    if not path.exists():
        pytest.skip("素材不在本机，跳过")
    if FRAME_RGB is None:
        pytest.skip("这个人没声明眼镜，跳过")

    image = Image.open(path).convert("RGBA")
    arr = np.array(image)
    span, pixels, area, subject_w = _glasses_measure(arr[..., :3], arr[..., 3])

    assert span > 0, f"{relative}：脸区里没有镜框色像素，眼镜没戴上"
    assert span >= subject_w * MIN_FRAME_SPAN_RATIO, (
        f"{relative}：脸区的镜框色只横跨 {span}px（主体宽 {subject_w}px，"
        f"不到 {MIN_FRAME_SPAN_RATIO:.0%}）——不像横跨两只眼睛的镜框"
    )
    assert pixels >= area * MIN_FRAME_AREA_RATIO, (
        f"{relative}：脸区镜框色只有 {pixels}px（占脸区 {pixels / area:.2%}），"
        f"不像有厚度的镜框"
    )


def test_the_glasses_judgement_fails_when_the_frames_are_removed():
    """注入验证：把镜框抹掉，判据必须塌下来。

    说明它量的是**眼镜**，不是脸区里别的东西——判据有效性自己也要被验。
    """
    from PIL import Image

    path = aim_paths.character_dir(SLUG) / f"{SLUG}_character_2k_nobg.png"
    if not path.exists():
        pytest.skip("主形象不在本机，跳过")

    arr = np.array(Image.open(path).convert("RGBA"))
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    span, pixels, area, subject_w = _glasses_measure(rgb, alpha)
    assert span >= subject_w * MIN_FRAME_SPAN_RATIO, "原图就没通过，注入没意义"

    # 把镜框连同它的抗锯齿边缘一起抹成皮肤色
    from scipy import ndimage

    box = _subject_box(rgb, alpha)
    top, bottom = _face_band(box, box[3] - box[1])
    frame = np.zeros(rgb.shape[:2], dtype=bool)
    frame[top:bottom] = _frame(rgb)[top:bottom]
    frame = ndimage.binary_dilation(frame, np.ones((7, 7)))
    stripped = rgb.copy()
    stripped[frame] = (176, 196, 210)      # 角色皮肤的浅蓝灰

    new_span, new_pixels, _, _ = _glasses_measure(stripped, alpha)
    assert new_span < subject_w * MIN_FRAME_SPAN_RATIO, (
        f"抹掉镜框后判据仍然通过（跨度 {new_span}px）——它量的不是眼镜"
    )
