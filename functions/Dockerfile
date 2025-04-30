# Use an official Python runtime as a parent image matching your Cloud Function runtime
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=True
ENV PORT=8080

# Set the working directory in the container
WORKDIR /app

# Install OS dependencies if needed (e.g., for certain ML libraries)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
# Use --default-timeout=1000 to avoid timeouts on large downloads like torch
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# --- Download and save the sentence-transformers model ---
# Create the target directory within the application directory
RUN mkdir -p /app/model
# Download the model using a Python script within the build
# This runs during 'docker build' or 'gcloud builds submit'
RUN python -c "from sentence_transformers import SentenceTransformer; \
    model_name = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'; \
    print(f'---> Downloading model {model_name} during build...'); \
    model = SentenceTransformer(model_name); \
    model.save('/app/model'); \
    print('---> Model downloaded and saved to /app/model.')"
# --- Model download finished ---

# Copy the rest of the application code (main.py, src folder, etc.) into the container
COPY . .

# No CMD needed for Firebase Functions deployment via gcloud/Firebase CLI
# The platform uses buildpacks to determine the entry point based on main.py
# If deploying to Cloud Run directly, you might need:
# CMD ["functions-framework", "--target=YOUR_FUNCTION_NAME"]
