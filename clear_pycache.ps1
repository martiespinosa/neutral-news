<#
.SYNOPSIS
    Recursively finds and deletes all __pycache__ directories.

.DESCRIPTION
    This script searches for all __pycache__ directories starting from the 
    current directory and deletes them to clean up Python bytecode files.
    Reports the total space freed up in MB.

.NOTES
    Created for: projecte-2-dam-24-25-neutral-news
    Date: May 9, 2025
    Reason: It helps to free up disk space and keep the project directory clean.
    Since we're primarily deploying rather than executing locally, these cache files aren't providing us any benefit - they're just taking up space and potentially causing issues.
#>

# Get script's directory
$scriptPath = $PSScriptRoot
if (!$scriptPath) {
    $scriptPath = (Get-Location).Path
}

Write-Host "Starting __pycache__ cleanup from: $scriptPath" -ForegroundColor Cyan
Write-Host "Searching for __pycache__ directories..." -ForegroundColor Yellow

# Find all __pycache__ directories recursively
$pycacheDirs = Get-ChildItem -Path $scriptPath -Filter "__pycache__" -Recurse -Directory

# Count total directories found
$totalDirs = $pycacheDirs.Count
Write-Host "Found $totalDirs __pycache__ directories to clean." -ForegroundColor Yellow

if ($totalDirs -eq 0) {
    Write-Host "No __pycache__ directories found. Nothing to clean." -ForegroundColor Green
    exit 0
}

# Calculate total size
$totalSize = 0
foreach ($dir in $pycacheDirs) {
    $dirSize = (Get-ChildItem -Path $dir.FullName -Recurse -File | Measure-Object -Property Length -Sum).Sum
    $totalSize += $dirSize
}

# Convert to MB with 2 decimal places
$totalSizeMB = "{0:N2}" -f ($totalSize / 1MB)
Write-Host "Total size of __pycache__ directories: $totalSizeMB MB" -ForegroundColor Yellow

# Ask for confirmation before deletion
$confirmation = Read-Host "Do you want to delete all $totalDirs __pycache__ directories? (y/n)"
if ($confirmation -ne 'y') {
    Write-Host "Operation cancelled." -ForegroundColor Red
    exit 0
}

# Delete each __pycache__ directory
$deletedCount = 0
foreach ($dir in $pycacheDirs) {
    Write-Host "Removing: $($dir.FullName)" -ForegroundColor Gray
    
    try {
        Remove-Item -Path $dir.FullName -Recurse -Force
        $deletedCount++
    } 
    catch {
        Write-Host "Error removing $($dir.FullName): $_" -ForegroundColor Red
    }
}

# Summary
Write-Host "`nCleanup complete!" -ForegroundColor Green
Write-Host "Deleted $deletedCount of $totalDirs __pycache__ directories ($totalSizeMB MB freed)." -ForegroundColor Cyan

# Look for .pyc files that might be outside __pycache__ folders
$pycFiles = Get-ChildItem -Path $scriptPath -Filter "*.pyc" -Recurse -File

if ($pycFiles.Count -gt 0) {
    # Calculate size of pyc files
    $pycSize = ($pycFiles | Measure-Object -Property Length -Sum).Sum
    $pycSizeMB = "{0:N2}" -f ($pycSize / 1MB)
    
    Write-Host "`nFound $($pycFiles.Count) .pyc files outside of __pycache__ directories ($pycSizeMB MB)." -ForegroundColor Yellow
    
    $confirmPyc = Read-Host "Do you want to delete these .pyc files as well? (y/n)"
    if ($confirmPyc -eq 'y') {
        foreach ($file in $pycFiles) {
            Write-Host "Removing: $($file.FullName)" -ForegroundColor Gray
            Remove-Item -Path $file.FullName -Force
        }
        Write-Host "Deleted $($pycFiles.Count) .pyc files ($pycSizeMB MB freed)." -ForegroundColor Cyan
    }
}

# Calculate total space freed
$totalFreed = "{0:N2}" -f (($totalSize + ($pycFiles.Count -gt 0 -and $confirmPyc -eq 'y' ? $pycSize : 0)) / 1MB)
Write-Host "`nTotal disk space freed: $totalFreed MB" -ForegroundColor Green
Write-Host "`nOperation completed successfully." -ForegroundColor Green