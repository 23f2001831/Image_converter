import sys
import os

# Add the parent directory to the path so we can import the Flask app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from image_converter_flask import app

# This 'app' variable will be automatically detected by Vercel as a WSGI application
