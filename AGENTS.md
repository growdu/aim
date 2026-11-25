# AGENTS.md —— 给 AI 的中央入口（aim / 人物形象仓）

> **这是什么**：AI 协作者进入**本仓库**后**第一份**要读的文档。
> 它回答四个问题：本仓库是什么、有哪些模块、流水线怎么走、AI 该读什么不该碰什么。
>
> **给谁读**：AI 协作者。人读 [`README.md`](README.md)（本仓库总览）。
> **与别的仓的关系**（谁是谁的上下游、缝在哪儿）读仓库外的
> [`../aiv/REPOS.md`](../aiv/REPOS.md)。

---

## 一、本仓库是什么

**人这一侧**：把「这个人是谁」定下来，落成一份 JSON，交给 aiv 去渲染。

```
确认流程（音色定标 → 形象确认 → 人格确认 → 品牌片定稿）
   │
   ▼
models/<slug>/model.json          ← 这个人（唯一契约）
   │
   ▼
aiv（视频线）读它 → 渲染 → 成片
```

**下游**：[aiv](https://github.com/growduai/aiv)（视频线）。
**上游**：无——母稿树在 aik 那边，与本仓无关。

**缝是文件**：aiv 读 `model.json`，**不 import 本仓的任何模块**。

---

## 二、模块地图

| 模块 | 一级目录 | 它拥有 | 验收命令 |
|------|----------|--------|----------|
| **模型契约** | `models/` | `model.json`（这个人的唯一契约）、`brand_windows.json` | `python3 -m pytest tests/test_model.py -q` |
| **可复用件** | `aimkit/` | `model.py`（读模型）、`paths.py`（路径常量）、`fonts.py`（字体解析） | `python3 -m pytest tests/ -q` |
| **形象** | `scripts/character/` | 生成主形象、戴眼镜、盖铭牌、抹铭牌、合成白底 | `python3 -m pytest tests/test_character.py -q` |
| **品牌片** | `scripts/brand/` | 生成姿态与背景、重排底板文字、渲染片头片尾、配音 | `python3 -m pytest tests/test_brand.py -q` |
| **音色** | `scripts/voice/` | 量测参照录音、查多音字读音 | `python3 -m pytest tests/test_voice.py -q` |
| **线内规格** | `specs/` | 形象 / 音色 / 品牌片 / 人格四份规范 | ——（文档） |
| **素材** | `assets/` | 内置字体子集 + 出处台账（**入库**） | `python3 -m pytest tests/test_brand.py -q` |
| **本仓守卫** | `tests/` | 模型形状、字体出处与缺字、眼镜规格、人格、品牌片 | `python3 -m pytest tests/ -q` |

**跳过**（AI 不读不改）：`models/*/assets/`（这个人的素材，不入库）、
`models/*/_staging/`（加眼镜流程的中间产物）、`__pycache__/`、`.pytest_cache/`。

---

## 三、缝：下游在哪儿

**下游是 aiv**，缝是**一个文件**：

```json
// models/<slug>/model.json
{ "schema": 1, "person": "growdu", "voice": { "voice_id": "..." }, ... }
```

aiv 那边怎么指过来：

```toml
# aiv/video/config.toml
[model]
path = "../aim/models/growdu/model.json"
```

环境变量 `AIM_MODEL` 优先于配置文件。**aiv 不 import 本仓**——
它连 `aimkit/` 都不碰，只读那份 JSON。

---

## 四、AI 协作者的行为准则

### 4.1 必读

1. **本文件**（`AGENTS.md`）
2. [`README.md`](README.md)——本仓库总览
3. [`../aiv/plans/13-aim-人物模型仓.md`](../aiv/plans/13-aim-人物模型仓.md)——
   设计文档（**为什么是这些形状**）
4. [`../aiv/plans/14-aim-新仓.md`](../aiv/plans/14-aim-新仓.md)——
   实施计划（本仓怎么建起来的）

### 4.2 必守

- **跨仓零 import**：不 import aiv 的任何模块。缝是**文件**。
- **入库的是事实，不入库的是产物与素材**：素材只在本地，
  入库的是「它在哪」。
- **只做框架，不做内容**：规范写成可替换的规则模板——
  **规则**是框架的，**例子**是这个人的。
- **身份不在框架里**：人格、音色、形象、站名一律从 `model.json` 读，
  代码里不写死。换人只改模型，不改代码。
- **可空的字段就让它空着**：空 = 「还没定」，不是错误。
- **契约坏了才是硬错误**：`model.json` 读不了 / 形状不认识 → **报错退出**，
  不降级。素材文件不在 → **降级**，`doctor` 单独报。
- **文字一律用真实字体渲染**：模型生成的中英文会乱码。
- **相对路径的基准是 `model.json` 所在目录**——下游不需要知道本仓根在哪。
- **形状变了就涨 `schema`**：读不懂新形状时**报错退出**，不静默忽略。
- **验收按模块拆开**：谁改了什么，只有谁的套件会红。

### 4.3 禁碰

- **`models/*/assets/`**：这个人的素材，不入库。
- **`models/*/_staging/`**：加眼镜流程的中间产物。
- **`.remember/`、`.worktrees/`**：会话记忆与并行工作区，不是仓库的一部分。

### 4.4 改之前先跑

```bash
python3 -m pytest tests/ -q
```

**全套只有一条**——本仓小，模块之间又共用同一份 `model.json`，
拆开跑没有意义（不像 aiv 那样按模块拆）。

---

## 五、维护这份文件

- 模块增删时，**必须**更新 §二。
- 缝的位置变化时，**必须**更新 §三与 §四。
- 验收命令变化时，**必须**更新 [`acceptance/README.md`](acceptance/README.md)。
