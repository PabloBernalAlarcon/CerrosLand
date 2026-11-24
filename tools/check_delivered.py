"""Fail if anything in spec/delivered/ differs from the delivery as received."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERED = ROOT / "spec" / "delivered"
expected = {}
for line in (ROOT / "tools" / "delivered_checksums.sha256").read_text(encoding="utf-8").splitlines():
    digest, name = line.split(maxsplit=1)
    expected[name.removeprefix("./")] = digest
actual = {str(p.relative_to(DELIVERED)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in DELIVERED.rglob("*") if p.is_file()}
problems = [f"changed: {n}" for n in expected if n in actual and actual[n] != expected[n]]
problems += [f"missing: {n}" for n in expected if n not in actual]
problems += [f"added: {n}" for n in actual if n not in expected]
print("\n".join(problems) or f"spec/delivered untouched ({len(actual)} files)")
sys.exit(1 if problems else 0)
