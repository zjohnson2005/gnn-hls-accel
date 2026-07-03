# First-time GitHub push. Run from PowerShell:
#   cd C:\Users\zjohn\Projects\gnn-hls-accel
#   .\push_to_github.ps1

$ErrorActionPreference = "Stop"

$git = "C:\Program Files\Git\bin\git.exe"
if (-not (Test-Path $git)) {
    Write-Host "Git not found. Install Git for Windows from https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}

Set-Location $PSScriptRoot

Write-Host "Setting git identity..." -ForegroundColor Cyan
& $git config --global user.name "zjohnson2005"
& $git config --global user.email "zjohnson3375@gmail.com"

Write-Host "Staging files..." -ForegroundColor Cyan
& $git add .

Write-Host "Committing..." -ForegroundColor Cyan
& $git commit -m "Initial commit: GNN HLS + orchestration engine characterization"

Write-Host "Setting remote..." -ForegroundColor Cyan
& $git branch -M main
& $git remote remove origin 2>$null
& $git remote add origin https://github.com/zjohnson2005/gnn-hls-accel.git

Write-Host "Pushing (GitHub will ask for credentials)..." -ForegroundColor Cyan
Write-Host "  Username: zjohnson2005"
Write-Host "  Password: use a GitHub Personal Access Token, NOT your account password"
& $git push -u origin main

Write-Host "Done." -ForegroundColor Green
& $git log -1 --oneline
