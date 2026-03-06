import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

_wsgi_app = None

def application(environ, start_response):
    global _wsgi_app
    if _wsgi_app is None:
        import asyncio
        # uvloop کو ڈس ایبل کریں تاکہ Passenger کریش نہ ہو
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        
        from app.main import app
        from a2wsgi import ASGIMiddleware
        _wsgi_app = ASGIMiddleware(app)
        
    return _wsgi_app(environ, start_response)
