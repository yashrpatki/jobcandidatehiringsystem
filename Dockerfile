FROM python:3.11-slim

# Install system dependencies required for PDF conversion and OCR

RUN apt-get update && apt-get install -y 
poppler-utils 
tesseract-ocr 
tesseract-ocr-eng 
&& rm -rf /var/lib/apt/lists/*

# Set working directory

WORKDIR /app

# Copy requirements first for better Docker layer caching

COPY requirements.txt .

# Install Python dependencies

RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project

COPY . .

# Render provides the PORT environment variable

EXPOSE 10000

# Start Flask application with Gunicorn

CMD gunicorn --bind 0.0.0.0:$PORT app:app
