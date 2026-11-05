from __future__ import annotations

import argparse
from pathlib import Path


OLD = '''            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0", "--port", str(port), "--proxy-headers",
            "--forwarded-allow-ips", "*",
'''
NEW = '''            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0",  # nosec B104 - Railway ingress requires binding inside the container.
            "--port", str(port),
'''


def patch_runtime_source(source: str) -> str:
    """Stop trusting arbitrary X-Forwarded-* senders; this app does not consume proxy headers."""
    if OLD not in source:
        if NEW in source and "--forwarded-allow-ips" not in source:
            return source
        raise ValueError("Expected exactly the reviewed Uvicorn proxy configuration in runtime.py")
    updated = source.replace(OLD, NEW, 1)
    if OLD in updated or updated.count("--forwarded-allow-ips") != source.count("--forwarded-allow-ips") - 1:
        raise ValueError("Runtime proxy hardening patch did not apply cleanly")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the reviewed Railway proxy trust hardening")
    parser.add_argument("runtime_file", type=Path)
    args = parser.parse_args()
    original = args.runtime_file.read_text(encoding="utf-8")
    updated = patch_runtime_source(original)
    if updated != original:
        args.runtime_file.write_text(updated, encoding="utf-8")
        print(f"PATCHED {args.runtime_file}")
    else:
        print(f"ALREADY_PATCHED {args.runtime_file}")


if __name__ == "__main__":
    main()
