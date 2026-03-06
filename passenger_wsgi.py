import sys, os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(__file__))

from a2wsgi import ASGIMiddleware
from app.main import app

# Passenger looks for 'application'
application = ASGIMiddleware(app)
