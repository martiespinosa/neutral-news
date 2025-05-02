FROM python:3.10-slim

ENV PYTHONUNBUFFERED=True
ENV PORT=8080

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

RUN mkdir -p /app/model
RUN python -c "from sentence_transformers import SentenceTransformer; \
    model_name = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'; \
    print(f'---> Downloading model {model_name} during build...'); \
    model = SentenceTransformer(model_name); \
    model.save('/app/model'); \
    print('---> Model downloaded and saved to /app/model.')"

COPY . .
EXPOSE 8080
CMD ["functions-framework", "--target=fetch_news", "--port=8080"]