import sys, os

# ورچوئل اینوائرنمنٹ کا راستہ (Path) سیٹ کریں
INTERP = "/home/esabaqco/virtualenv/demo.esabaq.com/3.11/bin/python"
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.append(os.getcwd())

from a2wsgi import ASGIMiddleware
from app.main import app

# یہ cPanel کے Passenger کو بتاتا ہے کہ ایپ کہاں ہے
application = ASGIMiddleware(app)
