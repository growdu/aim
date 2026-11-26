# aim —— 人物形象仓

> **这是什么**：**装「人」**的仓。
> 音色、音调、形象、人格、品牌片——确认完之后，落成**一份 JSON**
> （`models/<slug>/model.json`），再由脚本把它渲染成**这个人的**
> 素材与片子。
>
> **JSON 是索引与参数，不是这个人本身**——人 = 规则（`specs/`）
> × 契约（`model.json`）× 产物（PNG / MP4 / WAV）。见
> [`specs/平台契约.md`](specs/平台契约.md)。
>
> **下游**读这份 JSON 与它指到的素材。**缝是文件**：下游只**读**，
> **不 import 本仓的任何模块**。
>
> **本仓自足**：不 import 别的仓，也不依赖别的仓——只有一个外部环境依赖
> （`ffmpeg` / `ffprobe`）与一份内置字体。

---

## 一、一句话

```
确认流程（音色定标 → 形象确认 → 人格确认 → 品牌片定稿）
   │
   ▼
models/<slug>/model.json          ← 这个人（唯一契约）
   │
   ▼
下游读它 → 渲染 → 成片
```

**元数据里不许出现媒体文件**——只有路径。媒体是素材，**不入库**。
入库的是「它在哪」，不是「它本身」。

## 二、目录

| 目录 | 装什么 |
| --- | --- |
| `models/<slug>/` | **这个人的模型**：`model.json`（契约）+ `brand_windows.json`（配乐窗口决策）。素材在 `assets/` 下，**不入库** |
| `aimkit/` | **可复用的那部分**：`model.py`（读模型）、`look.py`（形象规格与配色）、`paths.py`（路径常量）、`fonts.py`（字体解析） |
| `scripts/character/` | 形象侧：生成主形象、戴眼镜、盖铭牌、抹铭牌、合成白底 |
| `scripts/brand/` | 品牌片侧：生成姿态与背景、重排底板文字、渲染片头片尾、配音 |
| `scripts/voice/` | 音色侧：量测参照录音、查多音字读音 |
| `scripts/build_model.py` | 把确认结果归一化并写成 `model.json`（**校验通过才写**） |
| `scripts/doctor.py` | 体检：这个人的契约与素材齐不齐（**只报告，不改**） |
| `specs/` | 线内规格：平台契约、形象规范、音色规范、品牌片规范、人格规范 |
| `tests/` | 本仓的守卫：模型形状、字体出处与缺字、眼镜规格、人格、品牌片、**换人回归**、**不写死人** |
| `assets/fonts/` | **内置字体子集**（跨机决定版式，入库）+ 出处台账 `SOURCE.json` |

## 三、模型长什么样

`models/<slug>/model.json`（当前这个人是 `models/growdu/model.json`）：

| 段 | 管什么 | 可空？ |
| --- | --- | --- |
| `schema` | 形状版本号——形状变了就涨 | 否 |
| `person` | 这个人的标识（= 目录名） | 否 |
| `identity` | 站名 / 角色 / 定位 / 受众 / 禁忌 / 系列感 | 可空 |
| `voice` | 音色 id、pitch、speed、emotion、实测特征、多音字替换表 | `voice_id` 不可空 |
| `look` | 长什么样（外观描述） | 可空 |
| `look_spec` | 形象规格：眼镜款式与镜框色、衣服色、胸口图标色、铭牌字色、耳麦 | 可空（没声明 = 不戴眼镜） |
| `persona` | **一整段**人格文字（不是关键词数组） | 可空 |
| `brand` | 品牌词、标语、落版、片头片尾文案与片子位置、`backgrounds`（两张背景的生成 prompt）、`colors`（底板的深色 / 浅色） | 可空 |
| `assets` | 素材的**路径**（`mascot` `avatar` `pose_sheet` …） | 可空 |

**相对路径的基准是 `model.json` 所在目录**（= `models/<slug>/`）。
这样下游不需要知道本仓根在哪：基准就是 `Path(model_path).parent`。

## 四、规矩

- **跨仓零 import**：下游只**读** `model.json`，不 import 本仓的任何模块。
  缝是**文件**。
- **入库的是事实，不入库的是产物与素材**：素材（立绘、姿态表、头像、
  品牌片底板、样例视频）是使用者的东西，只在本地；入库的是「它在哪」。
- **只做框架，不做内容**：规范写成可替换的规则模板——**规则**是框架的，
  **例子**是这个人的。
- **身份不在框架里**：人格、音色、形象、站名一律从 `model.json` 读，
  代码里不写死。**换人只改模型，不改代码**——
  眼镜规格、衣服色、背景 prompt、底板配色都在模型里，代码只管读
  （`tests/test_no_hardcoded_person.py` 盯着）。
- **没声明 = 没有**：这个人不戴眼镜，加眼镜流程整体跳过；
  没有衣服色，铭牌检测走通用路径。**不拿默认值糊过去**。
- **文字一律用真实字体渲染**：模型生成的中英文会乱码——铭牌、底板、
  片头片尾上的字全部由代码写上去。
- **空 = 「还没定」**，不是错误；**契约坏了才是硬错误**（读不了就报错退出）。

## 五、怎么跑

```bash
# 装依赖（Linux 上优先用系统包，见 requirements/dev.txt）
pip install -r requirements/dev.txt

# 装内置字体（跨机版式一致靠它）
python3 scripts/install_font.py
python3 scripts/install_font.py --check

# 写出模型（校验通过才写）
python3 scripts/build_model.py --person <slug> --out models/<slug>/model.json

# 体检：契约与素材齐不齐（只报告，不改）
python3 scripts/doctor.py

# 本仓守卫
python3 -m pytest tests/ -q
```

**生成流程要 mcode-tools CLI**（`scripts/character/_mcode.py` 调它）：
那是**素材生产**用的，测试不碰网络。

## 六、给 AI 协作者

给 AI 协作者的入口是 [`AGENTS.md`](AGENTS.md)。
验收矩阵在 [`acceptance/README.md`](acceptance/README.md)。
