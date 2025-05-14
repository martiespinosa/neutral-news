#!/bin/bash

echo "Submitting build to Cloud Build..."
if ! gcloud builds submit --config cloudbuild.yaml .; then
    echo "Cloud Build submission failed." >&2
    exit 1
fi
echo "Cloud Build submission successful."

echo "Deploying service to Cloud Run..."
if ! gcloud run deploy fetch-news-service \
  --image gcr.io/neutralnews-ca548/fetch-news-image \
  --platform managed \
  --region us-central1 \
  --memory 4096M \
  --cpu 2 \
  --timeout 540 \
  --set-secrets=OPENAI_API_KEY=openai-api-key:latest \
  --allow-unauthenticated \
  --cpu-boost \
  --max-instances 2; then
    echo "Cloud Run deployment failed." >&2
    exit 1
fi
echo "Cloud Run deployment successful."
