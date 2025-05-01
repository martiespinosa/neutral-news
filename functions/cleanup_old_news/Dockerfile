FROM python:3.10-slim

ENV PYTHONUNBUFFERED=True
ENV PORT=8080

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY . .
EXPOSE 8080
CMD ["functions-framework", "--target=cleanup_old_news", "--port=8080"]