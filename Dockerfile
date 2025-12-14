# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for audio playback (optional, ignore errors)
RUN apt-get update || true && \
    apt-get install -y --no-install-recommends ffmpeg || true && \
    apt-get clean || true && \
    rm -rf /var/lib/apt/lists/* || true

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

# Run the bot with a delay to let Lavalink start
CMD ["sh", "-c", "sleep 15 && python bot.py"]
