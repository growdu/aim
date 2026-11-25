"""aim 的测试共用件。

**只做一件事**：把仓根放进 `sys.path`，好让 `import aimkit` 找得到。
别的什么都不做——aim 的测试不依赖任何别的仓。
"""
from __future__ import annotations

import sys
from pathlib import Path

AIM_ROOT = Path(__file__).resolve().parents[1]
if str(AIM_ROOT) not in sys.path:
    sys.path.insert(0, str(AIM_ROOT))
