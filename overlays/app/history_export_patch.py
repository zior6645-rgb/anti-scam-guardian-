from __future__ import annotations

import ast
import sys
from pathlib import Path

MARKER = "# AntiScam Guardian: authenticated JSON history attachment downloads."


def patch_main_source(source: str) -> str:
    if MARKER in source:
        return source

    tree = ast.parse(source)
    app_assignments = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "app" for target in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "FastAPI"
    ]
    if len(app_assignments) != 1:
        raise ValueError(f"Expected one FastAPI app assignment, found {len(app_assignments)}")

    imports = ""
    if "import json\n" not in source:
        imports += "import json\n"
    if "import secrets\n" not in source:
        imports += "import secrets\n"
    if "import time\n" not in source:
        imports += "import time\n"
    if "from fastapi.responses import JSONResponse, Response" not in source:
        imports += "from fastapi.responses import JSONResponse, Response\n"

    if imports:
        future_nodes = [
            node for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "__future__"
        ]
        line_end = max((node.end_lineno for node in future_nodes), default=0)
        lines = source.splitlines(keepends=True)
        source = "".join(lines[:line_end]) + imports + "".join(lines[line_end:])
        tree = ast.parse(source)
        app_assignments = [
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "app" for target in node.targets)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "FastAPI"
        ]

    app_line = app_assignments[0].end_lineno
    lines = source.splitlines(keepends=True)
    insertion = '''

# AntiScam Guardian: authenticated JSON history attachment downloads.
_HISTORY_EXPORTS: dict[str, tuple[float, bytes]] = {}

@app.post("/api/history/export")
def create_history_export(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
) -> dict:
    telegram_id, username = _authorized_user(x_telegram_init_data)
    upsert_user(telegram_id, username)

    now = time.monotonic()
    for old_token, (expires_at, _body) in list(_HISTORY_EXPORTS.items()):
        if expires_at <= now:
            _HISTORY_EXPORTS.pop(old_token, None)

    items = recent_scans(telegram_id, 1000000000)
    body = json.dumps(items, ensure_ascii=False, indent=2).encode("utf-8")
    token = secrets.token_urlsafe(32)
    _HISTORY_EXPORTS[token] = (now + 180, body)

    public_base = os.getenv(
        "PUBLIC_BASE_URL",
        "https://anti-scam-guardian-bot-production.up.railway.app",
    ).rstrip("/")
    if not public_base.startswith("https://"):
        raise HTTPException(status_code=503, detail="A public HTTPS base URL is required.")
    return {"url": public_base + "/api/history/export/" + token, "filename": "antiscam-guardian-history.json"}


@app.get("/api/history/export/{token}", name="download_history_export")
def download_history_export(token: str):
    item = _HISTORY_EXPORTS.pop(token, None)
    if item is None or item[0] <= time.monotonic():
        return Response(status_code=404)
    return Response(
        content=item[1],
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="antiscam-guardian-history.json"',
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
'''
    updated = "".join(lines[:app_line]) + insertion + "".join(lines[app_line:])
    ast.parse(updated)
    return updated


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python history_export_patch.py app/main.py")
    path = Path(sys.argv[1])
    original = path.read_text(encoding="utf-8")
    updated = patch_main_source(original)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print(f"PATCHED authenticated history attachment endpoint in {path}")
    else:
        print(f"ALREADY_PATCHED {path}")


if __name__ == "__main__":
    main()
