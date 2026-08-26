FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The gateway container itself doesn't need a Docker daemon inside it — sandboxed code
# execution happens via docker-compose's sandbox-runner / DockerSandbox on the host.
# Leave REQUIRE_DOCKER_SANDBOX unset (defaults to true) in the real deployment so a
# missing daemon fails loudly instead of silently running code with host access.

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]