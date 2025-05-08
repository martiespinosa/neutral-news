#!/bin/bash

echo "Submitting build to Cloud Build..."
gcloud builds submit --config cloudbuild.yaml .
if [ $? -ne 0 ]; then
    echo "Error: Cloud Build submission failed." >&2
    exit $?
fi
echo "Cloud Build submission successful."

echo "Deploying service to Cloud Run..."
gcloud run deploy cleanup-old-news-service \
  --image gcr.io/neutralnews-ca548/cleanup-old-news-image \
  --platform managed \
  --region us-central1 \
  --memory 4096M \
  --cpu 1 \
  --timeout 360 \
  --allow-unauthenticated
if [ $? -ne 0 ]; then
    echo "Error: Cloud Run deployment failed." >&2
    exit $?
fi
echo "Cloud Run deployment successful."
