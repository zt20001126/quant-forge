"""验证新框架包骨架可从 src 布局导入。"""

import unittest
import sys
from pathlib import Path


# 源码树测试显式加入 src；安装后的用户无需这段测试路径设置。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))


class PackageSkeletonTest(unittest.TestCase):
    """项目骨架阶段的最低导入检查。"""

    def test_quant_package_exposes_version(self) -> None:
        import quant

        self.assertEqual(quant.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
