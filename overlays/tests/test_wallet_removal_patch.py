import tempfile
import unittest
from pathlib import Path

from apply_wallet_removal_patch import apply_wallet_removal


class WalletRemovalPatchTests(unittest.TestCase):
    def test_removes_manifest_endpoint_and_preserves_health_route(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "static").mkdir()
            (root / "static" / "tonconnect-manifest.json").write_text("{}", encoding="utf-8")
            (root / "main.py").write_text(
                'from fastapi.responses import FileResponse, HTMLResponse, JSONResponse\n\n'
                'def build_tonconnect_manifest(public_base_url: str) -> dict:\n'
                '    return {"url": public_base_url}\n\n'
                '@app.get("/tonconnect-manifest.json")\n'
                'def tonconnect_manifest() -> JSONResponse:\n'
                '    return JSONResponse(build_tonconnect_manifest("https://example.com"))\n\n'
                '@app.get("/health")\n'
                'def health():\n'
                '    return {"ok": True}\n',
                encoding="utf-8",
            )
            (root / "config.py").write_text(
                "    # This lets the Mini App and TON Connect manifest use Railway's HTTPS domain\n"
                "    # without requiring the operator to buy or manage a domain.\n"
                "public_base_url = 'https://example.com'\n"
                "    # A public domain can be generated after the first Railway deploy. Until then,\n"
                "    # the bot remains usable through commands and the Mini App button stays hidden.\n"
                "    # The manifest endpoint returns 503 until an HTTPS origin is configured.\n"
                "webapp_url = public_base_url\n",
                encoding="utf-8",
            )
            (root / "legal.py").write_text(
                'TERMS = """Old text about Pro and connecting a wallet."""\n\n'
                'PRIVACY = """Old text about TON Connect."""\n',
                encoding="utf-8",
            )

            self.assertTrue(apply_wallet_removal(root))
            main = (root / "main.py").read_text(encoding="utf-8")
            config = (root / "config.py").read_text(encoding="utf-8")
            legal = (root / "legal.py").read_text(encoding="utf-8")

            self.assertNotIn("tonconnect", main.lower())
            self.assertNotIn("JSONResponse", main)
            self.assertIn('@app.get("/health")', main)
            self.assertNotIn("TON Connect", config)
            self.assertIn("webapp_url = public_base_url", config)
            self.assertNotIn("TON Connect", legal)
            self.assertNotIn("Pro entitlement", legal)
            self.assertFalse((root / "static" / "tonconnect-manifest.json").exists())

            snapshot = {p.name: p.read_text(encoding="utf-8") for p in (root / "main.py", root / "config.py", root / "legal.py")}
            self.assertFalse(apply_wallet_removal(root))
            self.assertEqual(snapshot, {p.name: p.read_text(encoding="utf-8") for p in (root / "main.py", root / "config.py", root / "legal.py")})


if __name__ == "__main__":
    unittest.main()
