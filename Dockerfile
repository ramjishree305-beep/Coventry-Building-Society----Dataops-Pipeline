FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline/ pipeline/

RUN useradd -m appuser && mkdir -p /app/data /app/logs && chown -R appuser /app
USER appuser

CMD ["python", "-m", "pipeline.main"]
