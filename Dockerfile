FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY image_converter_flask.py .
COPY . .

# Expose port
EXPOSE 5000

# Run the application with proper PORT expansion
CMD gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 2 --timeout 120 image_converter_flask:app
