import sys
import os
import asyncio

# Force default asyncio loop to avoid uvloop crashing during Passenger forks
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

# راستے کو پکا کریں (Folder path)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from a2wsgi import ASGIMiddleware
    from app.main import app
    
    # We wrap the ASGI app into WSGI
    _asgi_app = ASGIMiddleware(app)
    
    # Custom application wrapper to catch ANY request-time errors
    def application(environ, start_response):
        try:
            return _asgi_app(environ, start_response)
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [f"Request Error:\n{err}".encode('utf-8')]

except Exception as e:
    # اگر امپورٹ کے دوران کوئی ایرر آئے
    def application(environ, start_response):
        import traceback
        err = traceback.format_exc()
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [f"Import Error:\n{err}".encode('utf-8')]

