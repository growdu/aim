# 验收 —— 本仓自己验自己（aim / 人物形象仓）

> **原则**：**一条命令**——本仓小，模块之间又共用同一份 `model.json`，
> 拆开跑没有意义。
> 本仓只验自己，不验别的仓。

---

## 一、命令与 Expected

数字是 **2026-11-26** 实测的（Linux / Python 3.x）。

| # | 命令 | 跑的是什么 | Expected |
| --- | --- | --- | --- |
| 1 | `python3 -m pytest tests/ -q` | **全套**：模型形状、字体、形象、人格、品牌片、素材入库、**通用性** | **164 passed / 18 skipped** |
| 2 | `python3 -m pytest tests/test_model.py -q` | 模型契约：形状校验、相对路径基准、`schema` 涨版、**不猜用哪个人**、底板配色 | 20 passed |
| 3 | `python3 -m pytest tests/test_build_model.py -q` | 收拢确认结论：保留原值、不编身份、坏形状不写 | 9 passed |
| 4 | `python3 -m pytest tests/test_fonts.py -q` | 字体解析：族名解析、缺字探针、hinting 关掉 | 7 passed |
| 5 | `python3 -m pytest tests/test_voice.py -q` | 音色：替换表、多音字规则、参数取自模型 | 8 passed |
| 6 | `python3 -m pytest tests/test_character.py -q` | 形象：眼镜规格 ↔ 规范 ↔ prompt、素材位置跟模型一致 | 10 passed |
| 7 | `python3 -m pytest tests/test_persona.py -q` | 人格：一整段文字、关键词列表已退休、规范 ↔ 模型一致 | 7 passed |
| 8 | `python3 -m pytest tests/test_brand.py -q` | 品牌片：字体出处与缺字守卫、文案与**底板配色**取自模型 | 15 passed |
| 9 | `python3 -m pytest tests/test_assets_are_tracked.py -q` | 素材入库：用户素材不入库、内置字体与授权台账要入库 | 11 passed |
| 10 | `python3 -m pytest tests/test_brand_scripts.py -q` | 品牌片脚本：脚本只引用模型里声明的素材 | 7 passed |
| 11 | `python3 -m pytest tests/test_character_assets.py -q` | 形象素材：立绘 / 头像在不在、是不是模型说的那份 | 2 passed / 5 skipped |
| 12 | `python3 -m pytest tests/test_clear_badge.py -q` | 「无标牌」徽章：素材在不在、规格对不对 | 2 passed / 6 skipped |
| 13 | `python3 -m pytest tests/test_glasses_assets.py -q` | 眼镜素材：眼镜图在不在、是不是模型说的那份 | 4 skipped |
| 14 | `python3 -m pytest tests/test_stamp_badge.py -q` | 印章徽章：素材在不在、规格对不对 | 11 passed / 3 skipped |
| 15 | `python3 -m pytest tests/test_no_hardcoded_person.py -q` | **通用性**：代码里不许写死任何一个人（从模型反推） | 2 passed |
| 16 | `python3 -m pytest tests/test_person_swap.py -q` | **通用性**：换一个完全不同的人，整套流程必须跑得通 | 7 passed |
| 17 | `python3 -m pytest tests/test_cli.py -q` | **入口**：每条脚本都要会答 `--help`；**每条入口脚本都得进命令表**；**`./aim` 得有可执行位**（git 记 100755） | 37 passed |
| 18 | `python3 -m pytest tests/test_docs.py -q` | **文档**：仓内相对链接不许断；教程不许没了 | 9 passed |

**每条命令都在仓根跑。**

**那 18 条 skip 全是同一件事：素材不在本机。**
立绘、头像、眼镜图、徽章这些**生成素材**要联网、要消耗额度（见 §三），
所以 CI 里没有。跳过的只是「这个文件在不在」那几问——**被测的代码都跑了**。
每条 skip 都带一句原因，不静默跳过。

### 跑之前：内置字体要在

```bash
python3 scripts/install_font.py
python3 scripts/install_font.py --check
```

CI 里是同一条。**字体不在，缺字探针就没有判据**——
那几条守卫要么跳过、要么红成「系统里根本没有这个族」。

---

## 二、实测数字（2026-11-26）

| 项 | 实测 |
| --- | --- |
| `model.json` 大小 | 4855 字节 |
| 模型分段 | `schema` `person` `identity` `voice` `look` `persona` `brand` `assets` `look_spec`（9 段） |
| `brand` 段键数 | 18（含 `backgrounds` 与 `colors`） |
| `assets` 段键数 | 5（`source` `mascot` `mascot_plain` `avatar` `pose_sheet`） |
| 内置字体 cmap | 7546 个码位 |
| GB 2312-80 全集 | 7445 个字符，**缺 0 个** |
| 字体子集三面 | 3.36 / 3.44 / 3.32 MiB（上限 5 MiB） |

---

## 三、明确不做的验收

- ❌ **素材生成流程的端到端**（`generate_character.py` / `render_brand.py`）——
  它们要 mcode-tools CLI、消耗生成额度、还要真素材在场。
  CI 里**跑不了**，也不该跑。
- ❌ **样例视频的时长/画面验收**——样例视频不入库（使用者的东西）。
- ❌ **「全套测试合跑一遍」之外的重复收集**——本仓只有一条命令。

---

## 四、CI

| 工作流 | 跑什么 |
| --- | --- |
| `.github/workflows/aim.yml` | 装内置字体 → 跑 `python3 -m pytest tests/ -q` |

**本仓不 checkout 别的仓**——它不依赖任何别的仓。

**CI 用 runner 自带的系统 Python**（ubuntu-24.04 上是 3.12），
**不装 `actions/setup-python`**——那会把 `python3` 换成 toolcache 里的另一个
Python，而 apt 的 `python3-cairo` 进的是系统 Python，两个不是一个：
`import cairo` 失败 → 退到 pip 源码编译 pycairo → runner 上没有 cairo 的
开发头文件 → 编译失败 → 整条工作流红。
（2026-11-25 实测踩过；工作流里那条注释写着同样的事。）
