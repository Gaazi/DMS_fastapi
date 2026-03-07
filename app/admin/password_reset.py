"""
Admin Password Reset Page
─────────────────────────
/admin/reset-password/{user_id}  → GET  (form دکھائیں)
/admin/reset-password/{user_id}  → POST (password بدلیں)
"""
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from app.core.database import get_session
from app.models.auth import User
from app.logic.auth import pwd_context

router = APIRouter(prefix="/admin", tags=["Admin Password Reset"])

_STYLE = """
<style>
  body { font-family: sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; }
  .card { max-width: 480px; margin: 80px auto; background: #1e293b;
          border-radius: 12px; padding: 2rem; box-shadow: 0 8px 32px #0005; }
  h2   { margin-top:0; color:#7dd3fc; }
  label{ display:block; margin-bottom:.4rem; font-size:.9rem; color:#94a3b8; }
  input{ width:100%; padding:.7rem 1rem; border-radius:8px; border:1px solid #334155;
         background:#0f172a; color:#e2e8f0; font-size:1rem; box-sizing:border-box; margin-bottom:1.2rem; }
  .btn  { padding:.7rem 1.5rem; border-radius:8px; border:none; cursor:pointer; font-size:1rem; }
  .save { background:#3b82f6; color:#fff; }
  .back { background:#334155; color:#e2e8f0; text-decoration:none;
          display:inline-block; padding:.7rem 1.5rem; border-radius:8px; }
  .ok   { background:#166534; border:1px solid #15803d; color:#bbf7d0;
          padding:.8rem 1rem; border-radius:8px; margin-bottom:1rem; }
  .err  { background:#7f1d1d; border:1px solid #b91c1c; color:#fca5a5;
          padding:.8rem 1rem; border-radius:8px; margin-bottom:1rem; }
</style>
"""

@router.get("/reset-password/{user_id}", response_class=HTMLResponse)
async def reset_password_form(
    request: Request,
    user_id: int,
    session: Session = Depends(get_session)
):
    # Admin session چیک کریں
    if not request.session.get("admin_id"):
        return RedirectResponse("/admin/login")

    user = session.get(User, user_id)
    if not user:
        return HTMLResponse("<h2>User not found</h2>", status_code=404)

    msg = request.query_params.get("msg", "")
    msg_html = f'<div class="ok">✅ {msg}</div>' if msg else ""

    html = f"""<!DOCTYPE html>
<html><head><title>پاس ورڈ ری سیٹ | DMS Admin</title>{_STYLE}</head>
<body>
<div class="card">
  <h2>🔑 پاس ورڈ ری سیٹ</h2>
  <p style="color:#94a3b8;">یوزر: <strong style="color:#7dd3fc;">{user.username}</strong></p>
  {msg_html}
  <form method="post">
    <label>نیا پاس ورڈ</label>
    <input type="password" name="new_password" placeholder="نیا پاس ورڈ" required>
    <label>دوبارہ پاس ورڈ</label>
    <input type="password" name="confirm_password" placeholder="تصدیق کریں" required>
    <div style="display:flex;gap:1rem;align-items:center;">
      <button class="btn save" type="submit">محفوظ کریں</button>
      <a class="back" href="/admin/user/list">← واپس</a>
    </div>
  </form>
</div>
</body></html>"""
    return HTMLResponse(html)


@router.post("/reset-password/{user_id}", response_class=HTMLResponse)
async def reset_password_submit(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    session: Session = Depends(get_session)
):
    if not request.session.get("admin_id"):
        return RedirectResponse("/admin/login")

    user = session.get(User, user_id)
    if not user:
        return HTMLResponse("<h2>User not found</h2>", status_code=404)

    if new_password != confirm_password:
        html = f"""<!DOCTYPE html>
<html><head><title>پاس ورڈ ری سیٹ | DMS Admin</title>{_STYLE}</head>
<body><div class="card">
  <h2>🔑 پاس ورڈ ری سیٹ</h2>
  <p style="color:#94a3b8;">یوزر: <strong style="color:#7dd3fc;">{user.username}</strong></p>
  <div class="err">❌ دونوں پاس ورڈ ایک جیسے نہیں ہیں!</div>
  <form method="post">
    <label>نیا پاس ورڈ</label>
    <input type="password" name="new_password" required>
    <label>دوبارہ پاس ورڈ</label>
    <input type="password" name="confirm_password" required>
    <div style="display:flex;gap:1rem;">
      <button class="btn save" type="submit">محفوظ کریں</button>
      <a class="back" href="/admin/user/list">← واپس</a>
    </div>
  </form>
</div></body></html>"""
        return HTMLResponse(html)

    if len(new_password) < 6:
        return HTMLResponse(f"""<!DOCTYPE html><html><head>{_STYLE}</head>
<body><div class="card"><div class="err">❌ پاس ورڈ کم از کم 6 حروف کا ہونا چاہیے۔</div>
<a class="back" href="/admin/reset-password/{user_id}">← واپس</a></div></body></html>""")

    user.password = pwd_context.hash(new_password)
    session.add(user)
    session.commit()

    return RedirectResponse(
        f"/admin/reset-password/{user_id}?msg=پاس+ورڈ+کامیابی+سے+بدل+گیا",
        status_code=303
    )
