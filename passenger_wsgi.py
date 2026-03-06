import sys
import os

# راستے کو پکا کریں (Folder path)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    from a2wsgi import ASGIMiddleware
    from app.main import app
    application = ASGIMiddleware(app)
except Exception as e:
    # اگر کوئی ایرر آئے تو وہ برائوزر میں نظر آئے
    def application(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [f"Error loading application: {str(e)}".encode()]
