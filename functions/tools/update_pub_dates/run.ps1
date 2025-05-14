# Define parameters
param(
    [int]$batch = 450,
    [int]$limit = 0,
    [switch]$force = $false,
    [switch]$test = $false
)

# Check if Python is installed
try {
    $pythonVersion = python --version
    Write-Host "✅ Python is installed: $pythonVersion"
} catch {
    Write-Host "❌ Python is not installed. Please install Python 3.x before continuing."
    exit 1
}

# Check and install firebase-admin package if needed
Write-Host "Checking for firebase-admin package..."
$packageCheck = python -c "import firebase_admin" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "🔄 Installing firebase-admin package..."
    pip install firebase-admin
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install firebase-admin. Please check your internet connection and permissions."
        exit 1
    }
    Write-Host "✅ firebase-admin installed successfully"
} else {
    Write-Host "✅ firebase-admin is already installed"
}

# Try to install pytz for better timezone handling
Write-Host "Checking for pytz package..."
$pytzCheck = python -c "import pytz" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "🔄 Installing pytz package for better timezone handling..."
    pip install pytz
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️ Could not install pytz. Will continue without it (timezone display may be affected)."
    } else {
        Write-Host "✅ pytz installed successfully"
    }
} else {
    Write-Host "✅ pytz is already installed"
}

# Get the script path (relative to this script)
$scriptPath = Join-Path $PSScriptRoot "update_pub_dates.py"

# Verify script exists
if (-not (Test-Path $scriptPath)) {
    Write-Host "❌ Python script not found at: $scriptPath"
    exit 1
}

# Build command arguments
$arguments = ""
if ($batch -ne 450) {
    $arguments += " --batch $batch"
}
if ($limit -gt 0) {
    $arguments += " --limit $limit"
}
if ($force) {
    $arguments += " --force"
}
if ($test) {
    $arguments += " --test"
}

# Display execution information
Write-Host ""
Write-Host "📊 Execution information:"
Write-Host "  - Script: $scriptPath"
Write-Host "  - Batch size: $batch documents per batch"
if ($limit -gt 0) {
    Write-Host "  - Document limit: $limit documents"
} else {
    Write-Host "  - Document limit: No limit (all documents)"
}
Write-Host "  - Force mode: $force"
Write-Host "  - Test mode: $test"
Write-Host ""

# Execute the Python script with parameters
Write-Host "▶️ Running update script to convert pub_date fields to Timestamp format..."
python $scriptPath$arguments

Write-Host "✅ Script execution completed"
