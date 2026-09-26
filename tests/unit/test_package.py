"""验证 QuantForge 包元数据与版本。"""

import unittest

import quant


class PackageTest(unittest.TestCase):
    def test_quant_package_exposes_version(self) -> None:
        self.assertEqual(quant.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
