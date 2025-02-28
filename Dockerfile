FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libavdevice-dev \
    libavfilter-dev \
    libopus-dev \
    libvpx-dev \
    pkg-config \
    libsrtp2-dev \
    libopusfile-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose ports for HTTP and WebSocket
EXPOSE $PORT

# Run the application
CMD ["python", "-m", "server.main"] 