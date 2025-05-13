# Build stage for dependencies
ARG PYTHON_VERSION=3.10
FROM python:${PYTHON_VERSION}-slim AS builder

# Set working directory and configure PATH
WORKDIR /app
ENV PATH="/usr/local/bin:$PATH"

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Update pip first
RUN pip install --upgrade pip

# Install newspaper3k and its dependencies first
RUN pip install --no-cache-dir lxml lxml_html_clean newspaper3k==0.2.8 && \
    python -c "from newspaper import Article; print('Newspaper import successful')"

# Install base requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 torch>=1.9.0 --extra-index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Install functions-framework globally
RUN pip install --no-cache-dir functions-framework && \
    which functions-framework && \
    functions-framework --help

# Download and cache the model in a separate step
RUN mkdir -p /app/model
RUN python -c "from sentence_transformers import SentenceTransformer; \
    model_name = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'; \
    print('---> Downloading model ' + model_name); \
    model = SentenceTransformer(model_name); \
    model.save('/app/model'); \
    print('---> Model downloaded and saved to /app/model')"

# Final stage with minimal dependencies
FROM python:${PYTHON_VERSION}-slim

# Install curl for healthcheck BEFORE switching users
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/usr/local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local /usr/local

# Copy pre-downloaded model
COPY --from=builder /app/model /app/model

# Copy application code
COPY . .

# Create a non-root user and give permissions
RUN useradd -m appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /usr/local/bin

# Verify functions-framework is in path
RUN which functions-framework

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Create a simple health check endpoint
RUN echo '#!/bin/sh\n\
echo "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nHealthy"' > /app/health.sh && \
    chmod +x /app/health.sh

# Improved health check - check if service is running on port instead of endpoint
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/_ah/health || exit 1

# Set entrypoint
CMD ["functions-framework", "--target=fetch_news", "--port=8080"]