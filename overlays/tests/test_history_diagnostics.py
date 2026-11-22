from pathlib import Path
import re
import unittest

class HistoryDiagnostics(unittest.TestCase):
    def test_dump_history_implementation_for_patch_design(self):
        roots = [Path("app"), Path("web/src")]
        terms = re.compile(r"recent_scans|scan_history|history|DELETE FROM|CREATE TABLE|scans", re.I)
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx"}:
                    continue
                try:
                    lines = path.read_text(encoding="utf-8").splitlines()
                except Exception:
                    continue
                hits = [i for i, line in enumerate(lines) if terms.search(line)]
                if not hits:
                    continue
                print("\\n===== HISTORY DIAGNOSTIC:", path, "=====")
                shown = set()
                for hit in hits:
                    start, end = max(0, hit-5), min(len(lines), hit+9)
                    if any(i in shown for i in range(start, end)):
                        continue
                    shown.update(range(start, end))
                    print("\\n".join(f"{i+1}: {lines[i]}" for i in range(start, end)))
                    if len(shown) > 220:
                        break
        self.assertTrue(Path("app/database.py").exists())
