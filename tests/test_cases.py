"""Golden-output tests: each check, run on its case folder, must print exactly
what tests/golden/ records. Regenerate after an intended change with
UPDATE_GOLDEN=1 python -m unittest discover tests, then read the diff."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"
CASES = [(l.split("\t") + [""])[:3] for l in (ROOT / "tests" / "cases.tsv").read_text().splitlines() if l.strip()]


def output(check, case):
    # Relative paths on purpose: several scanners skip any path containing a
    # `tmp` or `fixtures` component, which an absolute checkout path can hit.
    r = subprocess.run([sys.executable, "-I", "deadtests", "run", check, f"cases/{case}"],
                       cwd=ROOT, capture_output=True, text=True)
    return "\n".join(sorted((r.stdout + r.stderr).strip().splitlines())) + "\n"


class GoldenTest(unittest.TestCase):
    def test_every_check_has_a_case(self):
        sys.path.insert(0, str(ROOT))
        import importlib.machinery, importlib.util
        loader = importlib.machinery.SourceFileLoader("deadtests", str(ROOT / "deadtests"))
        spec = importlib.util.spec_from_loader("deadtests", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        self.assertEqual(set(mod.CHECKS), {c for c, _, _ in CASES})

    def test_golden(self):
        for check, case, kind in CASES:
            with self.subTest(check=check, case=case):
                got = output(check, case)
                path = GOLDEN / f"{check}__{case}.txt"
                if os.environ.get("UPDATE_GOLDEN"):
                    path.write_text(got)
                    continue
                self.assertTrue(path.exists(), f"missing golden file {path.name}")
                self.assertEqual(got, path.read_text())
                findings = [l for l in got.splitlines() if l.startswith("cases/") or ":" in l.split(" ")[0]]
                if kind == "negative":
                    self.assertEqual(findings, [], "a negative control must stay clean")
                else:
                    self.assertTrue(findings, "a positive case must produce at least one finding")


if __name__ == "__main__":
    unittest.main()
