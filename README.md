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

### 1.1 交付形式

**三样**：**CLI**（仓根的 `./aim`）、**skill**、**agent**。

| 谁 | 拿什么 | 怎么用 |
| --- | --- | --- |
| **人**（生产素材与片子） | **CLI** | clone 仓 → 装依赖与字体 → `./aim <阶段> <动作>`。参数原样转交给脚本，退出码原样传回；每条脚本也都能单独跑（都有 `--help`，`tests/test_cli.py` 盯着） |
| **AI / 工具**（别的 agent） | **skill + agent** | 装**独立分发包**（**不在本仓**）：skill 教它流程与铁律，agent 是专职跑活的。两者都调**同一个 `./aim`**——**实现只有一份** |
| **下游**（别的程序） | **一份 JSON 契约** | **只读 `models/<slug>/model.json`** 与它指到的素材。**不 import 本仓**——`aimkit/` 是仓内实现，不是对外 API |
| **CI** | — | GitHub Actions：装内置字体 → `python3 -m pytest tests/ -q` |

```bash
./aim --help              # 列全部命令
./aim character           # 列这一组的动作
./aim character badge --help
```

**为什么 skill / agent 不在本仓**：本仓是**跑东西的仓**，不是 Claude Code 的配置仓。
放进来，两边都要改对方的形状。**分发包**里只有「模板 + 安装脚本」——
铁律与流程**指的是本仓那份**（`AGENTS.md` / `specs/`），不是抄一份；
命令表在**安装时从本仓现生成**，单一出处，不会过期。

**为什么不是 pip 包**：aim 的产物是**素材**（使用者的东西，版权与口味是他们的），
不是一个能 `pip install` 的库。做成包反而会**假装**它有对外 API——
而它没有：**缝是文件**。

**依赖**：`requirements/dev.txt`（Linux 上优先用系统包）+ 仓内内置字体
+ `ffmpeg` / `ffprobe` +（生成类脚本）`mcode-tools` CLI 与额度。

## 二、目录

| 目录 | 装什么 |
| --- | --- |
| `models/<slug>/` | **这个人的模型**：`model.json`（契约）+ `brand_windows.json`（配乐窗口决策）。素材在 `assets/` 下，**不入库** |
| `aimkit/` | **可复用的那部分**：`model.py`（读模型）、`look.py`（形象规格与配色）、`paths.py`（路径常量）、`fonts.py`（字体解析）、`cli.py`（命令表） |
| `aim` | **命令行入口**（仓根）：`aim <阶段> <动作> [参数…]`。是**门面**——命令表指向现有脚本，参数与退出码原样转交 |
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

## 五、怎么用

> **第一次用先读**：[`docs/使用教程.md`](docs/使用教程.md)——
> 从 clone 到出片，每一步敲什么、看到什么、缺东西会怎样。

### 5.1 输入

| 输入 | 从哪来 | 缺了会怎样 |
| --- | --- | --- |
| **人的确认结论** | 人写（音色定标 → 形象确认 → 人格确认 → 品牌片定稿） | 契约坏了 → **报错退出**，不降级 |
| **形象原型参考图** | `model.json` 的 `assets.source`（使用者的素材） | 不跑生成流程，直接用 `assets.mascot` 指的那张 |
| **已生成的素材** | `models/<slug>/assets/` | **降级**（渲染少一块），`doctor` 单独报 |
| **内置字体** | 仓内 `assets/fonts/`（入库） | 文字画不出来 → 报错（不画豆腐块） |
| **生成额度 + mcode-tools CLI** | 系统 | 生成类脚本跑不了（测试不碰网络） |
| **ffmpeg / ffprobe** | 系统 | 合成与配音跑不了 |

**空 = 「还没定」，不是错误**；**契约坏了才是硬错误**。

### 5.2 怎么跑

**入口是仓根的 `./aim`**（**在仓根跑**）：

```bash
# 装依赖（Linux 上优先用系统包，见 requirements/dev.txt）
pip install -r requirements/dev.txt

# 装内置字体（跨机版式一致靠它）
./aim font install
./aim font install --check

# 1) 建模：把确认结论归一化成契约（**校验通过才写**）
./aim model build --person <slug> --out models/<slug>/model.json

# 2) 体检：契约与素材齐不齐（只报告，不改）
./aim doctor

# 3) 生成本地素材（一条命令跑完整条链；产物留在本地，**不入库**）
./aim assets build

#    也可以单步跑（每一步都消耗生成额度）
./aim character generate      # 主形象 + 6 姿态表
./aim character glasses       # 戴眼镜（没声明眼镜就整体跳过）
./aim character white         # 透明底合成白底版
./aim character badge         # 盖铭牌（品牌词用真实字体写）
./aim character clear-badge   # 抹铭牌（平台判「过度营销」时用）

# 4) 出品牌片
./aim brand poses             # 点赞 / 挥手姿态
./aim brand backgrounds       # 两张 AI 背景（语义验收）
./aim brand audio             # 按窗口混成品音轨
./aim brand render            # 渲染片头 / 片尾

# 本仓守卫
python3 -m pytest tests/ -q
```

**素材按设计不入库**（版权与口味是使用者的），但**本机要有**——
跑回归前用 `./aim assets build` 生成到本地，那 19 个「素材不在本机」的
用例才真的跑起来（实测：190 passed / 19 skipped → **209 passed / 0 skipped**）。
见 [`docs/本地素材回路.md`](docs/本地素材回路.md)。

** `./aim` 是门面，实现是脚本**——参数原样转交、退出码原样传回，
所以每条脚本**也都能单独跑**（`python3 scripts/brand/render_brand.py --intro`）。
每条都有 `--help`。缺素材时它们**降级并说清楚缺什么**，不糊过去。
详见 [`scripts/character/readme.md`](scripts/character/readme.md) 与
[`scripts/brand/readme.md`](scripts/brand/readme.md)。

**指一个人**：脚本在 import 时就读模型，**不指就报错退出**——
设 `AIM_MODEL=models/<slug>/model.json`
（仓里有好几个人时**报错列出候选，绝不猜**）。

### 5.3 产出

| 产出 | 在哪 | 入库？ |
| --- | --- | --- |
| **契约** | `models/<slug>/model.json` | **是** |
| **配乐窗口决策** | `models/<slug>/brand_windows.json` | **是** |
| **内置字体子集 + 出处台账** | `assets/fonts/` | **是** |
| 主形象（白底 / 透明底）、6 姿态表、头像 | `models/<slug>/assets/character/` | 否（使用者的东西） |
| 品牌片姿态素材、背景图 | `models/<slug>/assets/brand/assets/` | 否 |
| 品牌片成片（mp4） | `models/<slug>/assets/brand/clips/` | 否 |
| 成品音轨（旁白 + 配乐） | `models/<slug>/assets/brand/audio/` | 否 |
| 参照录音 / 样音 | `models/<slug>/assets/voice/` | 否 |

**入库的是「它在哪」，不是「它本身」。** 下游按 `model.json` 指到的位置取用，
**不 import 本仓**——缝是文件。

## 六、给 AI 协作者

给 AI 协作者的入口是 [`AGENTS.md`](AGENTS.md)。
验收矩阵在 [`acceptance/README.md`](acceptance/README.md)。
