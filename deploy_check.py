import ast, os, re
from collections import Counter

print("=" * 55)
print("  FINAL DEPLOYMENT READINESS CHECK")
print("=" * 55)

# 1. Syntax
print("\n[1] Python Syntax...")
errors = []
for root, dirs, files in os.walk("app"):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if not f.endswith(".py"): continue
        path = os.path.join(root, f)
        try:
            with open(path, encoding="utf-8-sig") as fh:
                ast.parse(fh.read())
        except SyntaxError as e:
            errors.append(f"  FAIL {path}:{e.lineno}")
print("  OK All clean" if not errors else "\n".join(errors))

# 2. All imports
print("\n[2] Module Imports...")
mods = ["app.main","app.logic.finance","app.logic.students",
        "app.logic.institution","app.logic.courses","app.logic.staff",
        "app.logic.attendance","app.logic.payments","app.logic.audit",
        "app.logic.permissions","app.logic.guardian","app.logic.auth",
        "app.logic.exams","app.utils.context","app.utils.helper"]
ok = True
for mod in mods:
    try:
        __import__(mod, fromlist=[mod.split(".")[-1]])
    except Exception as e:
        print(f"  FAIL {mod}: {e}")
        ok = False
if ok: print("  OK All imports OK")

# 3. Route conflicts
print("\n[3] Route Conflicts...")
from fastapi.routing import APIRoute
from app.main import app
routes = [r for r in app.routes if isinstance(r, APIRoute)]
path_m = Counter((r.path, tuple(sorted(r.methods or []))) for r in routes)
dupes = {k:v for k,v in path_m.items() if v>1}
name_d = {n:c for n,c in Counter(r.name for r in routes).items() if c>1}
if dupes or name_d:
    for (p,m),c in dupes.items(): print(f"  FAIL PATH {p}: {c}x")
    for n,c in name_d.items(): print(f"  FAIL NAME {n}: {c}x")
else:
    print(f"  OK {len(routes)} routes, no conflicts")

# 4. Template broken includes
print("\n[4] Template Includes...")
tpl_dir = "app/templates"
broken = []
for root, dirs, files in os.walk(tpl_dir):
    for f in files:
        if not f.endswith(".html"): continue
        path = os.path.join(root, f)
        rel = os.path.relpath(path, tpl_dir)
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for i, line in enumerate(fh, 1):
                m = re.search(r"include\s+['\"]([^'\"]+)['\"]", line)
                if m:
                    inc = os.path.join(tpl_dir, m.group(1))
                    if not os.path.exists(inc):
                        broken.append(f"  FAIL {rel}:{i} -> {m.group(1)}")
if broken:
    for b in broken: print(b)
else:
    print("  OK All includes OK")

# 5. Config
print("\n[5] Config...")
try:
    from app.core.config import settings
    db_url = str(settings.DATABASE_URL)[:50]
    print(f"  OK DB: {db_url}")
    print(f"  OK Project: {settings.PROJECT_NAME} v{settings.VERSION}")
except Exception as e:
    print(f"  FAIL Config: {e}")

print("\n" + "=" * 55)
print("  DEPLOYMENT CHECK COMPLETE")
print("=" * 55)
