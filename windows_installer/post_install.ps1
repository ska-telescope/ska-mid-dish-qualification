# Get the user's home directory
$userHome = [Environment]::GetFolderPath("UserProfile")

# Define the source and target paths
$sourcePath = "$PSScriptRoot\disq.ini"
$targetPath = "$userHome\AppData\Local\SKAO\disq\disq.ini"

# Copy the default included ini file if one doesn't already exist
if (-not (Test-Path -Path $targetPath)) {
    Copy-Item -Path $sourcePath -Destination $targetPath -Force
}
