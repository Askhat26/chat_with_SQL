# Base Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies for SQLite + matplotlib
RUN apt-get update && apt-get install -y \
    sqlite3 libsqlite3-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (including index.html)
COPY . .

# Expose Flask default port
EXPOSE 5000

# Run Flask app
CMD ["python", "app.py"]
