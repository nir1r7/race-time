FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install deps first (better layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Make both entrypoints executable
RUN chmod +x /app/entrypoint-api.sh /app/entrypoint-poller.sh

EXPOSE 8000

# Default container behavior = run the API.
# The poller service will override the entrypoint in docker-compose / k8s.
ENTRYPOINT ["/app/entrypoint-api.sh"]
