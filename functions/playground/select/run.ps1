# Check if Python is installed
try {
    $pythonVersion = python --version
    Write-Host "✅ Python is installed: $pythonVersion"
} catch {
    Write-Host "❌ Python is not installed. Please install Python 3.x before continuing."
    exit 1
}

# Check and install required packages
$requiredPackages = @("firebase-admin", "tabulate")
foreach ($package in $requiredPackages) {
    Write-Host "Checking for $package package..."
    $packageCheck = python -c "import $($package.Replace('-','_'))" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "🔄 Installing $package package..."
        pip install $package
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Failed to install $package. Please check your internet connection and permissions."
            exit 1
        }
        Write-Host "✅ $package installed successfully"
    } else {
        Write-Host "✅ $package is already installed"
    }
}

# Get the script path - UPDATED FILENAME HERE
$scriptPath = Join-Path $PSScriptRoot "select_news.py"

# Verify script exists
if (-not (Test-Path $scriptPath)) {
    Write-Host "❌ Python script not found at: $scriptPath"
    exit 1
}

# Execute the Python script with interactive mode
Write-Host "▶️ Running Firebase document selector..."
python $scriptPath

Write-Host "✅ Script execution completed"