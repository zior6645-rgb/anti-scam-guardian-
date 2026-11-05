from __future__ import annotations

import unittest

from app.runtime_security_patch import OLD, NEW, patch_runtime_source


class RuntimeSecurityPatchTests(unittest.TestCase):
    def test_removes_wildcard_forwarded_header_trust(self):
        source = "import sys\nasync def run():\n    api = await asyncio.create_subprocess_exec(\n" + OLD + "    )\n"
        updated = patch_runtime_source(source)
        self.assertIn(NEW, updated)
        self.assertNotIn("--proxy-headers", updated)
        self.assertNotIn("--forwarded-allow-ips", updated)
        self.assertIn('"--host", "0.0.0.0"', updated)

    def test_patch_is_idempotent(self):
        source = "import sys\n" + NEW
        self.assertEqual(patch_runtime_source(source), source)

    def test_unexpected_runtime_configuration_fails_closed(self):
        with self.assertRaises(ValueError):
            patch_runtime_source('await create_subprocess_exec("--host", "0.0.0.0")')


if __name__ == "__main__":
    unittest.main()
