Write-Host "Submitting build to Cloud Build..."
gcloud builds submit --config cloudbuild.yaml .
if ($LASTEXITCODE -ne 0) {
    Write-Error "Cloud Build submission failed."
    exit $LASTEXITCODE
}
Write-Host "Cloud Build submission successful."

Write-Host "Deploying service to Cloud Run..."
gcloud run deploy cleanup-old-news-service `
  --image gcr.io/neutralnews-ca548/cleanup-old-news-image `
  --platform managed `
  --region us-central1 `
  --memory 4096M `
  --cpu 1 `
  --timeout 360 `
  --allow-unauthenticated
if ($LASTEXITCODE -ne 0) {
    Write-Error "Cloud Run deployment failed."
    exit $LASTEXITCODE
}
Write-Host "Cloud Run deployment successful."