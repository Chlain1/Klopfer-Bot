# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install FFmpeg, required to stream audio (YouTube/SoundCloud/etc.) directly into
# Discord voice channels without ever downloading tracks to disk.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create a non-root user to run the bot
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

USER botuser

CMD ["python", "bot.py"]
