# Use an official Python runtime as a parent image matching your Cloud Function runtime
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=True
ENV PORT=8080

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if needed for Firebase Firestore or other libraries)
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Copy the rest of the application code (main.py, src folder, etc.) into the container
COPY . .

# The platform uses buildpacks to determine the entry point based on main.py
# Use functions-framework to specify the target function
CMD ["functions-framework", "--target=cleanup_old_news", "--port=8080"]