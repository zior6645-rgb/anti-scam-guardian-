from pathlib import Path
import unittest

class HistoryDiagnostics(unittest.TestCase):
    def test_dump_exact_history_sections(self):
        specs = {
            "app/database.py": [(1, 220)],
            "app/main.py": [(1, 240)],
            "web/src/main.js": [(1, 190)],
            "web/index.html": [(1, 260)],
        }
        for name, ranges in specs.items():
            path = Path(name)
            if not path.exists():
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            for start, end in ranges:
                print("\\n===== EXACT SOURCE", name, start, end, "=====")
                print("\\n".join(f"{i+1}: {lines[i]}" for i in range(start-1, min(end, len(lines)))))
        self.assertTrue(Path("app/database.py").exists())
