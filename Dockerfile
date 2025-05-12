# Use Python 3.9 slim image as base
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP app
ENV FLASK_ENV production

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        git \
        cron \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p instance uploads/uploaded uploads/pending uploads/printing uploads/completed uploads/archive logs

# Set up cron job
COPY maintenance-cron /etc/cron.d/maintenance-cron
RUN chmod 0644 /etc/cron.d/maintenance-cron \
    && crontab /etc/cron.d/maintenance-cron

# Set permissions
RUN chown -R www-data:www-data /app
RUN chmod -R 755 /app

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Start both cron and the application
CMD service cron start && waitress-serve --port=8080 --call app:create_app 