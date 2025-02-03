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
$wizardImgPath = "$projectRoot\src\ska_mid_disq\ui_resources\images\installer.png"
$headerImgPath = "$projectRoot\src\ska_mid_disq\ui_resources\images\wombat_logo.png"
$distName = "DiSQ-$version-win64"
$internalPath = "$projectRoot\dist\$distName\_internal"
$exePath = "$projectRoot\dist\$distName\$distName.exe"
$scriptPath = "$projectRoot\$installerDir\post_install.bat"
$ifpPath = "$projectRoot\$installerDir\disq.ifp"

# Define pyinstaller arguments as individual items in an array
$arguments = @(
    "--name", $distName, 
    "--clean", "--noconfirm", "--windowed", 
    "--add-data", "src/ska_mid_disq/ui_resources/main_window.ui:ska_mid_disq/ui_resources", 
    "--add-data", "src/ska_mid_disq/default_logging_config.yaml:ska_mid_disq", 
    "--add-data", "src/ska_mid_disq/weather_station_resources/weather_station_configs.json:ska_mid_disq/weather_station_resources", 
    "--add-data", "src/ska_mid_disq/weather_station_resources/weather_station.yaml:ska_mid_disq/weather_station_resources", 
    "--add-data", "src/ska_mid_disq/ui_resources/icons/skao.ico:.", 
    "--icon", "src/ska_mid_disq/ui_resources/icons/skao.ico", 
    "src/ska_mid_disq/gui_main.py"
)

# Call pyinstaller with the arguments
Write-Host "Building DiSQ version $version with PyInstaller..."
& pyinstaller @arguments
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
$text = $text -replace ".+\\dist\\DiSQ.*?\\_internal", $internalPath
$text = $text -replace ".+\\dist\\DiSQ.*?\\DiSQ.*?\.exe", $exePath
$text = $text -replace ".+\\$installerDir\\post_install.bat", $scriptPath
$text = $text -replace "<InstallPath>\\DiSQ.*?\.exe", "<InstallPath>\$distName.exe"

# Write the modified content back to the updated .ifp file
[System.IO.File]::WriteAllBytes($ifpPath, [System.Text.Encoding]::Default.GetBytes($text))

Write-Host "Load '$ifpPath' in InstallForge and build the installer!"
exit 0
