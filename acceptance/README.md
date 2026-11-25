# 验收 —— 本仓自己验自己（aim / 人物形象仓）

> **原则**：**一条命令**——本仓小，模块之间又共用同一份 `model.json`，
> 拆开跑没有意义（不像 aiv 那样按模块拆）。
> 跨仓只验接口，不验实现。

---

## 一、命令与 Expected

数字是 **2026-11-25** 实测的（Linux / Python 3.x）。

| # | 命令 | 跑的是什么 | Expected |
| --- | --- | --- | --- |
| 1 | `python3 -m pytest tests/ -q` | **全套**：模型形状、字体、形象、人格、品牌片 | **66 passed** |
| 2 | `python3 -m pytest tests/test_model.py -q` | 模型契约：形状校验、相对路径基准、`schema` 涨版 | 13 passed |
| 3 | `python3 -m pytest tests/test_build_model.py -q` | 收拢确认结论：保留原值、不编身份、坏形状不写 | 9 passed |
| 4 | `python3 -m pytest tests/test_fonts.py -q` | 字体解析：族名解析、缺字探针、hinting 关掉 | 7 passed |
| 5 | `python3 -m pytest tests/test_voice.py -q` | 音色：替换表、多音字规则、参数取自模型 | 7 passed |
| 6 | `python3 -m pytest tests/test_character.py -q` | 形象：眼镜规格 ↔ 规范 ↔ prompt、素材位置跟模型一致 | 9 passed |
| 7 | `python3 -m pytest tests/test_persona.py -q` | 人格：一整段文字、关键词列表已退休、规范 ↔ 模型一致 | 7 passed |
| 8 | `python3 -m pytest tests/test_brand.py -q` | 品牌片：字体出处与缺字守卫、文案取自模型 | 14 passed |

**每条命令都在仓根跑。**

### 跑之前：内置字体要在

```bash
python3 scripts/install_font.py
python3 scripts/install_font.py --check
```

CI 里是同一条。**字体不在，缺字探针就没有判据**——
那几条守卫要么跳过、要么红成「系统里根本没有这个族」。

---

## 二、跨仓的接口验收（从 aiv 那一侧看）

| 接口 | 从 → 到 | 怎么验 | Expected |
| --- | --- | --- | --- |
| 模型契约 | aim `models/<slug>/model.json` → aiv `pyv/model.py` | aiv 读得出 `person` / `voice` / `brand` / `assets` | 读得出；读不了就是**硬错误** |
| 素材位置 | aim `model.json` 的 `assets.mascot` → aiv 合成角色 | 路径相对 `model.json` 所在目录 | aiv 按 `model.json` 的目录解析即中 |
| 字体子集 | aim `assets/fonts/*.otf` ↔ aiv `video/pipeline/assets/fonts/*.otf` | **sha256 相同** | 两边字节一致（aiv 侧有守卫） |

**跨仓零 import**——上面三条全是**比文件**，没有一条是 import 对方的模块。

---

## 三、实测数字（2026-11-25）

| 项 | 实测 |
| --- | --- |
| `model.json` 大小 | 2704 字节 |
| 模型分段 | `schema` `person` `identity` `voice` `look` `persona` `brand` `assets`（8 段） |
| `brand` 段键数 | 16 |
| `assets` 段键数 | 5（`source` `mascot` `mascot_plain` `avatar` `pose_sheet`） |
| 内置字体 cmap | 7546 个码位 |
| GB 2312-80 全集 | 7445 个字符，**缺 0 个** |
| 字体子集三面 | 3.36 / 3.44 / 3.32 MiB（上限 5 MiB） |

---

## 四、明确不做的验收

- ❌ **素材生成流程的端到端**（`generate_character.py` / `render_brand.py`）——
  它们要 mcode-tools CLI、消耗生成额度、还要真素材在场。
  CI 里**跑不了**，也不该跑。
- ❌ **样例视频的时长/画面验收**——样例视频不入库（使用者的东西）。
- ❌ **「全套测试合跑一遍」之外的重复收集**——本仓只有一条命令。

---

## 五、CI

| 工作流 | 跑什么 |
| --- | --- |
| `.github/workflows/aim.yml` | 装内置字体 → 跑 `python3 -m pytest tests/ -q` |

**aim 不 checkout 别的仓**——它不依赖 aik，也不依赖 aiv。
（aiv 那边要 checkout 本仓，那是**它**的缝，不是本仓的。）
