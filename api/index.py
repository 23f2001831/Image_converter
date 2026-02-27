# api/index.py
# Vercel serverless function handler for Flask app
import sys
import os

# Add the parent directory to the path so we can import the Flask app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from image_converter_flask import app

# Export the Flask app as 'app' for Vercel's WSGI handler
# Vercel will automatically detect this and serve it
