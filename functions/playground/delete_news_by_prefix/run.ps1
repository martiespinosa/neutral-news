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

# Get the existing script path (relative to this script)
$scriptPath = Join-Path $PSScriptRoot "delete_news_by_prefix.py"

# Verify script exists
if (-not (Test-Path $scriptPath)) {
    Write-Host "❌ Python script not found at: $scriptPath"
    exit 1
}

# Execute the Python script
Write-Host "▶️ Running delete script..."
python $scriptPath

Write-Host "✅ Script execution completed"