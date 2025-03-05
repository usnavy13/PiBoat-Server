FROM python:3.9-slim

WORKDIR /app

# Install dependencies
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy web client requirements
COPY web_client/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy web client code
COPY web_client /app/

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV RELAY_SERVER=ws://relay-server:8000

# Expose port for web interface
EXPOSE $PORT

# Run the web client - use shell form for environment variable expansion
CMD python app.py --host 0.0.0.0 --relay-server $RELAY_SERVER --log-dir logs 