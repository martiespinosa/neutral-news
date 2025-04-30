# PowerShell script to deploy Cloud Functions using gcloud and Dockerfile

# --- Configuration ---
$PROJECT_ID = "neutralnews-ca548" # Replace with your Project ID
$REGION = "us-central1"          # Replace with your region
$REPO_NAME = "cloud-functions-docker" # Your chosen Artifact Registry repo name
$SECRET_NAME = "openai-api-key"   # Your Secret Manager secret name for the API key
$SECRET_VERSION = "latest"
$TIME_ZONE = "Europe/Madrid"     # Adjust timezone for schedules

# Construct Artifact Registry path
$ARTIFACT_REGISTRY_REPO = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

# --- Ensure Artifact Registry Repo Exists (Run manually if needed) ---
# Write-Host "Ensure Artifact Registry repository exists: $ARTIFACT_REGISTRY_REPO"
# gcloud artifacts repositories create $REPO_NAME --repository-format=docker --location=$REGION --description="Docker repository for Cloud Functions"

# --- Define Topic Names ---
$TOPIC_FETCH = "trigger-fetch-news"
$TOPIC_CLEANUP = "trigger-cleanup-old-news"

# --- Create Pub/Sub Topics (if they don't exist) ---
# Write-Host "Ensuring Pub/Sub topic $TOPIC_FETCH exists..."
# gcloud pubsub topics create $TOPIC_FETCH --quiet

# Write-Host "Ensuring Pub/Sub topic $TOPIC_CLEANUP exists..."
# gcloud pubsub topics create $TOPIC_CLEANUP --quiet
# Write-Host ""


# --- Deploy fetch-news (Pub/Sub Trigger Only) ---
Write-Host "Deploying fetch-news function..."
$FUNCTION_NAME_FETCH = "fetch-news"
$ENTRY_POINT_FETCH = "fetch_news"
$MEMORY_FETCH = "4096MB"
$TIMEOUT_FETCH = "540s"

gcloud functions deploy $FUNCTION_NAME_FETCH `
  --gen2 `
  --region=$REGION `
  --runtime=python310 `
  --source=./functions `
  --entry-point=$ENTRY_POINT_FETCH `
  --trigger-topic=$TOPIC_FETCH `
  --docker-repository=$ARTIFACT_REGISTRY_REPO `
  --memory=$MEMORY_FETCH `
  --timeout=$TIMEOUT_FETCH `
  --set-secrets="OPENAI_API_KEY=${SECRET_NAME}:${SECRET_VERSION}"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deployment of $FUNCTION_NAME_FETCH function failed."
    exit $LASTEXITCODE
}
Write-Host "$FUNCTION_NAME_FETCH function deployed successfully."
Write-Host ""

# --- Create Scheduler Job for fetch-news ---
Write-Host "Creating/Updating Cloud Scheduler job for fetch-news..."
$JOB_NAME_FETCH = "schedule-${FUNCTION_NAME_FETCH}"
$SCHEDULE_FETCH = "every 4 hours"
$MESSAGE_BODY_FETCH = '{"data": "trigger"}' # Simple JSON payload

# Use 'update' which also creates if it doesn't exist (upsert)
gcloud scheduler jobs update pubsub $JOB_NAME_FETCH `
    --schedule="$SCHEDULE_FETCH" `
    --topic=$TOPIC_FETCH `
    --message-body=$MESSAGE_BODY_FETCH `
    --time-zone=$TIME_ZONE `
    --location=$REGION

if ($LASTEXITCODE -ne 0) {
    Write-Error "Creation/Update of scheduler job $JOB_NAME_FETCH failed."
    # Decide if you want to exit here or continue with the next function
    # exit $LASTEXITCODE
}
Write-Host "Scheduler job $JOB_NAME_FETCH created/updated successfully."
Write-Host ""


# --- Deploy cleanup-old-news (Pub/Sub Trigger Only) ---
Write-Host "Deploying cleanup-old-news function..."
$FUNCTION_NAME_CLEANUP = "cleanup-old-news"
$ENTRY_POINT_CLEANUP = "cleanup_old_news"
$MEMORY_CLEANUP = "1024MB"
$TIMEOUT_CLEANUP = "300s"

gcloud functions deploy $FUNCTION_NAME_CLEANUP `
  --gen2 `
  --region=$REGION `
  --runtime=python310 `
  --source=./functions `
  --entry-point=$ENTRY_POINT_CLEANUP `
  --trigger-topic=$TOPIC_CLEANUP `
  --docker-repository=$ARTIFACT_REGISTRY_REPO `
  --memory=$MEMORY_CLEANUP `
  --timeout=$TIMEOUT_CLEANUP `
  --set-secrets="OPENAI_API_KEY=${SECRET_NAME}:${SECRET_VERSION}"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deployment of $FUNCTION_NAME_CLEANUP function failed."
    exit $LASTEXITCODE
}
Write-Host "$FUNCTION_NAME_CLEANUP function deployed successfully."
Write-Host ""

# --- Create Scheduler Job for cleanup-old-news ---
Write-Host "Creating/Updating Cloud Scheduler job for cleanup-old-news..."
$JOB_NAME_CLEANUP = "schedule-${FUNCTION_NAME_CLEANUP}"
$SCHEDULE_CLEANUP = "every 24 hours" # Or "every day 03:00"
$MESSAGE_BODY_CLEANUP = '{"data": "trigger"}' # Simple JSON payload

# Use 'update' which also creates if it doesn't exist (upsert)
gcloud scheduler jobs update pubsub $JOB_NAME_CLEANUP `
    --schedule="$SCHEDULE_CLEANUP" `
    --topic=$TOPIC_CLEANUP `
    --message-body=$MESSAGE_BODY_CLEANUP `
    --time-zone=$TIME_ZONE `
    --location=$REGION

if ($LASTEXITCODE -ne 0) {
    Write-Error "Creation/Update of scheduler job $JOB_NAME_CLEANUP failed."
    # Decide if you want to exit here
    # exit $LASTEXITCODE
}
Write-Host "Scheduler job $JOB_NAME_CLEANUP created/updated successfully."
Write-Host ""

Write-Host "All deployments and scheduler configurations finished."