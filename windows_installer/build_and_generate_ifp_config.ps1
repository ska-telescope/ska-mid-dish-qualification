# Set the working directory and version extraction
$projectRoot = Get-Location
$releaseFile = ".release"

# Read version from .release file
$version = (Get-Content $releaseFile | Where-Object { $_ -match "^release=" } | ForEach-Object { $_.Split('=')[1] }).Trim()

# Check if version was extracted
if (-not $version) {
    Write-Error "ERROR: Could not extract version from .release file."
    exit 1
}

# Define paths
$installerDir = "windows_installer"
$installerPath = "$projectRoot\$installerDir\DiSQ-$version-windows-x64.exe"
$wizardImgPath = "$projectRoot\src\ska_mid_disq\ui\images\installer.png"
$headerImgPath = "$projectRoot\src\ska_mid_disq\ui\images\wombat_logo.png"
$internalPath = "$projectRoot\dist\DiSQ\_internal"
$exePath = "$projectRoot\dist\DiSQ\DiSQ.exe"
$scriptPath = "$projectRoot\$installerDir\post_install.ps1"
$ifpPath = "$projectRoot\$installerDir\disq.ifp"

# Run PyInstaller with the specified version
Write-Host "Building DiSQ version $version with PyInstaller..."
$pyInstallerCmd = "pyinstaller --clean --noconfirm disq.spec"
$pyInstallerResult = Invoke-Expression $pyInstallerCmd
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: PyInstaller build failed."
    exit 1
}
Write-Host "PyInstaller build process completed successfully!"

# Copy disq.ini to the dist path
Write-Host "Copying disq.ini to $internalPath..."
Copy-Item -Path "disq.ini" -Destination $internalPath -Force
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: Failed to copy disq.ini to $internalPath."
    exit 1
}

# Read the .ifp file as bytes to preserve NUL characters
$content = [System.IO.File]::ReadAllBytes($ifpPath)

# Convert binary content to string
$text = [System.Text.Encoding]::Default.GetString($content)

# Perform replacements (preserving NUL characters)
Write-Host "Updating InstallForge project file with version $version and relative paths..."
$text = $text -replace "Program version = .+", "Program version = $version"
$text = $text -replace "Wizard image = .+", "Wizard image = $wizardImgPath"
$text = $text -replace "Header image = .+", "Header image = $headerImgPath"
$text = $text -replace "File = .+", "File = $installerPath"
$text = $text -replace "C:\\.*?_internal", $internalPath
$text = $text -replace "C:\\.*?DiSQ.exe", $exePath
$text = $text -replace "C:\\.*?post_install.ps1", $scriptPath

# Write the modified content back to the updated .ifp file
[System.IO.File]::WriteAllBytes($ifpPath, [System.Text.Encoding]::Default.GetBytes($text))

Write-Host "Load '$ifpPath' in InstallForge and build the installer!"
exit 0
