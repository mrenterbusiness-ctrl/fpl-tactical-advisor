# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=8080

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Run gunicorn on $PORT
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60 app:app
