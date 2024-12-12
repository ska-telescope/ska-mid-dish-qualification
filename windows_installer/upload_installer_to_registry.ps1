# Add your personal access token. DO NOT COMMIT IT TO THE REPO!
$token = ""

# Read version from .release file
$version = (Get-Content ".release" | Where-Object { $_ -match "^release=" } | ForEach-Object { $_.Split('=')[1] }).Trim()

# Check if version was extracted
if (-not $version) {
    Write-Error "ERROR: Could not extract version from .release file."
    exit 1
}

# Define variables for better readability
$filePath = ".\windows_installer\DiSQ-$version-windows-x64.exe"
$uploadUrl = "https://gitlab.com/api/v4/projects/47618837/packages/generic/DiSQ-GUI/$version/DiSQ-$version-windows-x64.exe"

# Use Invoke-WebRequest to upload the file
Invoke-WebRequest `
    -Uri $uploadUrl `
    -Method Put `
    -Headers @{ "PRIVATE-TOKEN" = $token } `
    -InFile $filePath

Write-Host "Successfully uploaded '$filePath' to DiSQ package registry! See https://gitlab.com/ska-telescope/ska-mid-disq/-/packages/"
exit 0