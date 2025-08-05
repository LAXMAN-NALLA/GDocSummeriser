FROM python:3.11-slim

WORKDIR /app

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose the correct port
EXPOSE 8000

# Make sure start.sh is executable
RUN chmod +x ./start.sh

# Use the shell script to start the app
CMD ["./start.sh"]
