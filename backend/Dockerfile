# Edezee backend. Builds a small image that runs the FastAPI app on $PORT.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

COPY requirements.lock ./

# Install from the hash-locked file and refuse source distributions, so no
# dependency can run a setup.py at install time. Regenerate the lock with:
#   pip-compile --generate-hashes --strip-extras -o requirements.lock requirements.txt
RUN pip install --no-cache-dir --only-binary :all: --require-hashes -r requirements.lock

COPY app ./app

# Run as a non-root user; the service is stateless and needs no write access.
RUN useradd --create-home --uid 1000 edezee
USER edezee

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
