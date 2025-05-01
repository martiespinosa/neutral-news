python3 -m venv venv
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create Python virtual environment."
    exit $LASTEXITCODE
}

.\venv\Scripts\Activate
# Note: Activating venv in a script doesn't persist for subsequent commands in the same script execution easily.
# Consider running gcloud directly or ensuring dependencies are met differently if needed.
# For now, assuming gcloud is in PATH and doesn't rely on the venv activation within the script itself.

Write-Host "Submitting build to Cloud Build..."
gcloud builds submit --tag gcr.io/neutralnews-ca548/fetch-news-image .
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
  --cpu 1 `
  --timeout 540 `
  --set-secrets=OPENAI_API_KEY=openai-api-key:latest `
  --allow-unauthenticated
if ($LASTEXITCODE -ne 0) {
    Write-Error "Cloud Run deployment failed."
    exit $LASTEXITCODE
}
Write-Host "Cloud Run deployment successful."

# Optional: Deactivate venv if needed, though script exit usually handles this.
deactivate