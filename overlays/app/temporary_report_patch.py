from __future__ import annotations

import ast
import sys
from pathlib import Path

MARKER = "# AntiScam Guardian: short-lived, single-use Telegram report downloads."


def _insert_imports(source: str) -> str:
    tree = ast.parse(source)
    if "from fastapi import Request" in source:
        return source
    future_nodes = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "__future__"]
    if future_nodes:
        line_end = max(node.end_lineno for node in future_nodes)
    elif tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, (ast.Str, ast.Constant)):
        line_end = tree.body[0].end_lineno
    else:
        line_end = 0
    lines = source.splitlines(keepends=True)
    imports = (
        "import os\\n"
        "import secrets\\n"
        "import time\\n"
        "from fastapi import Request\\n"
        "from fastapi.responses import JSONResponse, Response\\n"
    )
    return "".join(lines[:line_end]) + imports + "".join(lines[line_end:])


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

    source = _insert_imports(source)
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
        raise ValueError("FastAPI app assignment became ambiguous after import insertion")
    line_end = app_assignments[0].end_lineno
    lines = source.splitlines(keepends=True)
    insertion = """\\n
# AntiScam Guardian: short-lived, single-use Telegram report downloads.
_REPORT_DOWNLOADS: dict[str, tuple[float, bytes]] = {}
_REPORT_UPLOADS_BY_IP: dict[str, list[float]] = {}

@app.post("/api/reports")
async def create_temporary_report(request: Request):
    now = time.monotonic()
    client_ip = request.client.host if request.client else "unknown"
    recent = [stamp for stamp in _REPORT_UPLOADS_BY_IP.get(client_ip, []) if now - stamp < 60]
    if len(recent) >= 8:
        return JSONResponse({"detail": "Too many report requests; retry shortly."}, status_code=429)
    recent.append(now)
    _REPORT_UPLOADS_BY_IP[client_ip] = recent

    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "text/plain":
        return JSONResponse({"detail": "Only text/plain reports are accepted."}, status_code=415)
    body = await request.body()
    if not body or len(body) > 32768:
        return JSONResponse({"detail": "Report must contain 1 to 32768 bytes."}, status_code=413)

    for old_token, (expires_at, _body) in list(_REPORT_DOWNLOADS.items()):
        if expires_at <= now:
            _REPORT_DOWNLOADS.pop(old_token, None)
    token = secrets.token_urlsafe(24)
    _REPORT_DOWNLOADS[token] = (now + 120, body)
    public_base = os.getenv(
        "PUBLIC_BASE_URL",
        "https://anti-scam-guardian-bot-production.up.railway.app",
    ).rstrip("/")
    if not public_base.startswith("https://"):
        return JSONResponse({"detail": "A public HTTPS base URL is required."}, status_code=503)
    return {"url": public_base + "/api/reports/" + token}

@app.get("/api/reports/{token}", name="download_temporary_report")
async def download_temporary_report(token: str):
    item = _REPORT_DOWNLOADS.pop(token, None)
    if item is None or item[0] <= time.monotonic():
        return Response(status_code=404)
    return Response(
        content=item[1],
        media_type="text/plain",
        headers={
            "Content-Disposition": 'attachment; filename="antiscam-screening-report.txt"',
            "Access-Control-Allow-Origin": "https://web.telegram.org",
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
"""
    source = "".join(lines[:line_end]) + insertion + "".join(lines[line_end:])
    ast.parse(source)
    return source


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.temporary_report_patch app/main.py")
    path = Path(sys.argv[1])
    original = path.read_text(encoding="utf-8")
    updated = patch_main_source(original)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print(f"PATCHED {path}")
    else:
        print(f"ALREADY_PATCHED {path}")


if __name__ == "__main__":
    main()
