# Build the image using Cloud Build: Navigate to your fetch_news directory in the terminal and run:
# cd functions/fetch_news
# gcloud builds submit --tag gcr.io/neutralnews-ca548/fetch-news-image .
# cd functions/cleanup_old_news
# gcloud builds submit --tag gcr.io/neutralnews-ca548/cleanup-old-news-image .


#Deploy the image to Cloud Run: Deploy the built image as a Cloud Run service.
gcloud run deploy fetch-news-service `
  --image gcr.io/neutralnews-ca548/fetch-news-image `
  --platform managed `
  --region us-central1 `
  --memory 4096M `
  --cpu 1 `
  --timeout 540 `
  --set-secrets=OPENAI_API_KEY=openai-api-key:latest `
  --allow-unauthenticated `
  

gcloud run deploy cleanup-old-news-service `
  --image gcr.io/neutralnews-ca548/cleanup-old-news-image `
  --platform managed `
  --region us-central1 `
  --memory 4096M `
  --cpu 1 `
  --timeout 540 `
  --allow-unauthenticated `