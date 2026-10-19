from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from run_synthetic_contract_fixture import EXPECTED, build_fixture  # noqa: E402
from trace_dt.b01_reference import b01_component_scores  # noqa: E402


class PlatformFixtureTests(unittest.TestCase):
    def test_integrated_contract_fixture(self) -> None:
        payload = build_fixture()
        self.assertEqual(payload["gate"], "PASS")
        self.assertEqual(payload["observed_contract"], EXPECTED)

    def test_b01_each_ablation_changes_only_one_declared_component(self) -> None:
        values = b01_component_scores(
            {"ds1": [0.9, 0.4, 0.2], "ds2": [0.7, 0.2]},
            {"ds1": 1.0, "ds2": 0.5},
        )
        self.assertEqual(len(values), 6)
        self.assertEqual(len(set(values.values())), 6)


if __name__ == "__main__":
    unittest.main()
