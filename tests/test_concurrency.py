import concurrent.futures
import importlib.util
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

_COCKPIT = Path(__file__).resolve().parents[1] / "bin" / "cockpit"
spec = importlib.util.spec_from_file_location(
    "cockpit", _COCKPIT, loader=SourceFileLoader("cockpit", str(_COCKPIT))
)
cockpit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cockpit)


class ConcurrencyTests(unittest.TestCase):
    def test_parallel_appends_unique_ids(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / ".agent-cockpit"

            def one(i):
                ev = {
                    "type": "dispatch.sent",
                    "dispatch_id": cockpit.make_id(home, "dsp", "dispatch"),
                }
                cockpit.append_event(home, "dispatch", ev)
                return ev["dispatch_id"]

            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
                ids = list(ex.map(one, range(64)))
            self.assertEqual(
                len(ids), len(set(ids)), "duplicate ids generated under concurrency"
            )


if __name__ == "__main__":
    unittest.main()
