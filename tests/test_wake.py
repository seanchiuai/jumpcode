import importlib.util
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

_COCKPIT = Path(__file__).resolve().parents[1] / "bin" / "cockpit"
spec = importlib.util.spec_from_file_location(
    "cockpit", _COCKPIT, loader=SourceFileLoader("cockpit", str(_COCKPIT))
)
cockpit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cockpit)


class ResolvePaneTests(unittest.TestCase):
    SAMPLE = "%26\torchestrator\n%27\tfrontend-lead\n%28\tbackend-lead\n%29\tqa-lead\n"

    def test_resolves_exact_role(self):
        self.assertEqual(cockpit.resolve_pane(self.SAMPLE, "backend-lead"), "%28")

    def test_unknown_role_returns_none(self):
        self.assertIsNone(cockpit.resolve_pane(self.SAMPLE, "nope"))

    def test_ignores_panes_without_role(self):
        self.assertIsNone(cockpit.resolve_pane("%30\t\n", "orchestrator"))


if __name__ == "__main__":
    unittest.main()
