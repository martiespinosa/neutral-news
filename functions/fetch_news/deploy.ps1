Write-Host "Submitting build to Cloud Build..."
gcloud builds submit --config cloudbuild.yaml .
if ($LASTEXITCODE -ne 0) {
    Write-Error "Cloud Build submission failed."
    exit $LASTEXITCODE
}
Write-Host "Cloud Build submission successful."

Write-Host "Deploying service to Cloud Run..."
gcloud run deploy fetch-news-service `
  --image gcr.io/neutralnews-ca548/fetch-news-image `
  --platform managed `
  --region us-central1 `
  --memory 4096M `
  --cpu 2 `
  --timeout 540 `
  --set-secrets=OPENAI_API_KEY=openai-api-key:latest `
  --allow-unauthenticated `
  --cpu-boost `
  --max-instances 2

if ($LASTEXITCODE -ne 0) {
    Write-Error "Cloud Run deployment failed."
    exit $LASTEXITCODE
}
Write-Host "Cloud Run deployment successful at time $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"