# Copies exactly the files a Hugging Face Space needs into a cloned Space repo.
#
# Usage (from the survey-insight folder):
#   .\deploy\huggingface\prepare_space.ps1 -SpaceDir ..\survey-insight-api
#
# Then, inside the Space folder: git add -A; git commit -m "Deploy"; git push
param(
    [Parameter(Mandatory = $true)][string]$SpaceDir
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")

if (-not (Test-Path (Join-Path $SpaceDir ".git"))) {
    throw "$SpaceDir is not a git clone of your Space. Clone it first (see DEPLOYMENT.md)."
}

# Start from a clean copy of the app files (keeps the Space's .git folder).
foreach ($item in @("backend", "sample_data", "Dockerfile", ".dockerignore", "README.md")) {
    $target = Join-Path $SpaceDir $item
    if (Test-Path $target) { Remove-Item $target -Recurse -Force -Confirm:$false }
}

Copy-Item (Join-Path $repo "Dockerfile") $SpaceDir
Copy-Item (Join-Path $repo ".dockerignore") $SpaceDir
Copy-Item (Join-Path $PSScriptRoot "README.md") (Join-Path $SpaceDir "README.md")

New-Item -ItemType Directory -Force (Join-Path $SpaceDir "backend") | Out-Null
Copy-Item (Join-Path $repo "backend\requirements.txt") (Join-Path $SpaceDir "backend")
Copy-Item (Join-Path $repo "backend\survey_insight") (Join-Path $SpaceDir "backend") -Recurse
Get-ChildItem (Join-Path $SpaceDir "backend") -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -Confirm:$false

New-Item -ItemType Directory -Force (Join-Path $SpaceDir "sample_data") | Out-Null
Copy-Item (Join-Path $repo "sample_data\student_wellbeing_survey.csv") (Join-Path $SpaceDir "sample_data")

Write-Host "Space files ready in $SpaceDir. Next: cd there, then git add -A, git commit, git push."
