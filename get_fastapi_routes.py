from app.main import app
routes = []
for r in app.routes:
    if hasattr(r, "name"):
        routes.append(r.name)
with open("fastapi_routes.txt", "w") as f:
    for name in sorted(list(set(routes))):
        if name:
            f.write(name + "\n")
