FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN useradd --create-home appuser
USER appuser

CMD ["sh", "-c", "exec gunicorn \"gateway.app:create_app()\" --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 8 --timeout 60"]
