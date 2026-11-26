# AGENTS.md —— 给 AI 的中央入口（aim / 人物形象仓）

> **这是什么**：AI 协作者进入**本仓库**后**第一份**要读的文档。
> 它回答四个问题：本仓库是什么、有哪些模块、流水线怎么走、AI 该读什么不该碰什么。
>
> **给谁读**：AI 协作者。人读 [`README.md`](README.md)（本仓库总览）。
> 本仓**自足**：不 import 别的仓，也不依赖别的仓——缝是**一个文件**。

---

## 一、本仓库是什么

**人这一侧**：把「这个人是谁」定下来，落成一份 JSON（契约），
再由脚本把它渲染成**这个人的**素材与片子。

```
确认流程（音色定标 → 形象确认 → 人格确认 → 品牌片定稿）
   │
   ▼
models/<slug>/model.json          ← 这个人（唯一契约）
   │
   ▼
下游读它 → 渲染 → 成片
```

**下游**：读这份 JSON（与它指到的素材）去渲染成片。
**上游**：无。

**缝是文件**：下游读 `model.json`，**不 import 本仓的任何模块**。

**JSON 是索引与参数，不是这个人本身**——人 = 规则（`specs/`）
× 契约（`model.json`）× 产物（PNG / MP4 / WAV）。见
[`specs/平台契约.md`](specs/平台契约.md)。

---

## 二、模块地图

| 模块 | 一级目录 | 它拥有 | 验收命令 |
|------|----------|--------|----------|
| **模型契约** | `models/` | `model.json`（这个人的唯一契约）、`brand_windows.json` | `python3 -m pytest tests/test_model.py -q` |
| **可复用件** | `aimkit/` | `model.py`（读模型）、`look.py`（形象规格与配色）、`paths.py`（路径常量）、`fonts.py`（字体解析） | `python3 -m pytest tests/ -q` |
| **形象** | `scripts/character/` | 生成主形象、戴眼镜、合成白底 | `python3 -m pytest tests/test_character.py -q` |
| **形象素材** | `scripts/character/` | 眼镜图与主形象的位置对不对、是不是模型说的那份 | `python3 -m pytest tests/test_character_assets.py tests/test_glasses_assets.py -q` |
| **铭牌** | `scripts/character/` | 盖铭牌（`stamp_badge.py`）、抹铭牌（`clear_badge.py`）——找铭牌那块白矩形靠 `scipy.ndimage` | `python3 -m pytest tests/test_stamp_badge.py tests/test_clear_badge.py -q` |
| **品牌片** | `scripts/brand/` | 生成姿态与背景、重排底板文字、渲染片头片尾、配音 | `python3 -m pytest tests/test_brand.py -q` |
| **品牌片脚本** | `scripts/brand/` | 脚本只引用模型里声明的素材 | `python3 -m pytest tests/test_brand_scripts.py -q` |
| **音色** | `scripts/voice/` | 量测参照录音、查多音字读音 | `python3 -m pytest tests/test_voice.py -q` |
| **体检** | `scripts/doctor.py` | 契约与素材齐不齐（**只报告，不改**） | `python3 scripts/doctor.py` |
| **线内规格** | `specs/` | 平台契约 / 形象 / 音色 / 品牌片 / 人格五份规范 | ——（文档） |
| **素材** | `assets/` | 内置字体子集 + 出处台账（**入库**） | `python3 -m pytest tests/test_fonts.py -q` |
| **素材入库** | `tests/` | 用户素材不入库、内置字体与授权台账要入库 | `python3 -m pytest tests/test_assets_are_tracked.py -q` |
| **本仓守卫** | `tests/` | 模型形状、字体出处与缺字、眼镜规格、人格、品牌片 | `python3 -m pytest tests/ -q` |
| **通用性守卫** | `tests/` | 代码里不许写死任何一个人；换一个完全不同的人必须跑得通 | `python3 -m pytest tests/test_no_hardcoded_person.py tests/test_person_swap.py -q` |
| **入口守卫** | `tests/` | 每条脚本都要会答 `--help`（交付形式是命令行，就得能问） | `python3 -m pytest tests/test_cli.py -q` |

**跳过**（AI 不读不改）：`models/*/assets/`（这个人的素材，不入库）、
`models/*/_staging/`（加眼镜流程的中间产物）、`__pycache__/`、`.pytest_cache/`。

---

## 三、AI 协作者的行为准则

### 3.1 必读

1. **本文件**（`AGENTS.md`）
2. [`README.md`](README.md)——本仓库总览

### 3.2 必守

- **跨仓零 import**：下游只**读** `model.json`，不 import 本仓的任何模块。
  缝是**文件**。
- **入库的是事实，不入库的是产物与素材**：素材只在本地，
  入库的是「它在哪」。
- **只做框架，不做内容**：规范写成可替换的规则模板——
  **规则**是框架的，**例子**是这个人的。
- **身份不在框架里**：人格、音色、形象、站名一律从 `model.json` 读，
  代码里不写死。换人只改模型，不改代码。
  眼镜规格、衣服色、铭牌字色、耳麦、品牌片背景 prompt、底板配色都在模型里
  （`look_spec`、`brand.backgrounds` 与 `brand.colors`）。
- **不拿默认值糊过去**：这个人不戴眼镜（`look_spec.glasses` 没声明），
  加眼镜流程**整体跳过**；身份没写就**空着**，不编一句占位符。
  糊过去了，下游就分不清「定错了」和「还没定」。
- **可空的字段就让它空着**：空 = 「还没定」，不是错误。
- **契约坏了才是硬错误**：`model.json` 读不了 / 形状不认识 → **报错退出**，
  不降级。素材文件不在 → **降级**，`doctor` 单独报。
- **文字一律用真实字体渲染**：模型生成的中英文会乱码。
- **相对路径的基准是 `model.json` 所在目录**——下游不需要知道本仓根在哪。
- **形状变了就涨 `schema`**：读不懂新形状时**报错退出**，不静默忽略。
- **涨了 `schema`，契约的每一端都要认**：缝是文件，**每一端各有一份读取器**，
  每一份各认一个版本号。本仓涨了，**下游那份读取器不跟着涨**，
  下游读到的就是「比它认识的旧」→ **报错退出**（那是对的），
  但**得有人去改那一端**——报错信息落在下游，根因在上游这一头。
  涨版本号之前先想清楚：**还有谁在读这份契约。**
- **不猜用哪个人**：仓里有好几个人时报错列出候选，**绝不猜**
  （猜错就是拿别人的事实去生成这个人的素材与片子）。
- **验收按模块拆开**：谁改了什么，只有谁的套件会红。

### 3.3 禁碰

- **`models/*/assets/`**：这个人的素材，不入库。
- **`models/*/_staging/`**：加眼镜流程的中间产物。
- **`.remember/`、`.worktrees/`**：会话记忆与并行工作区，不是仓库的一部分。

### 3.4 改之前先跑

```bash
python3 -m pytest tests/ -q
```

**全套只有一条**——本仓小，模块之间又共用同一份 `model.json`，
拆开跑没有意义。

> **跑之前：依赖要在**（Linux 上**优先用系统包**，见 `requirements/dev.txt`）：
> `python3-cairo python3-numpy python3-pil python3-pytest python3-scipy`，
> 外加 `fontTools`（只能 pip 装）。
> **`scipy` 不是可选项**——铭牌识别（`scipy.ndimage`）与读音验收
> （`scipy.linalg`）都要它。2026-11-25 搬脚本的时候依赖声明没跟着搬，
> CI 里 22 条用例红在 `No module named 'scipy'`。

---

## 四、维护这份文件

- 模块增删时，**必须**更新 §二。
- 契约或缝的形状变化时，**必须**更新 §一与 §三。
- 验收命令变化时，**必须**更新 [`acceptance/README.md`](acceptance/README.md)。
