#!/bin/bash

# Read version from .release file
if [ ! -f .release ]; then
    echo "ERROR: .release file not found."
    exit 1
fi

version=$(grep "^release=" .release | cut -d'=' -f2 | tr -d '[:space:]')
# CPU architecture of host detected automatically.
# Ideally we should build for "universal2" but often the Python binary is only available
# for the native architecture (x86_64 or arm64).
arch=$(uname -m)
dist_name="DiSQ-$version-macos-$arch"

# Check if version was extracted
if [ -z "$version" ]; then
    echo "ERROR: Could not extract version from .release file."
    exit 1
fi

# Run PyInstaller with the specified version
echo "Building DiSQ version $version with PyInstaller..."
pyinstaller --clean --noconfirm --onefile --name $dist_name \
    --target-architecture $arch \
    --add-data "src/ska_mid_disq/ui/dishstructure_mvc.ui:ska_mid_disq/ui" \
    --add-data "src/ska_mid_disq/default_logging_config.yaml:ska_mid_disq" \
    "src/ska_mid_disq/mvcmain.py"
    # -i skao.icns

if [ $? -ne 0 ]; then
    echo "ERROR: PyInstaller build failed."
    exit 1
fi

echo "PyInstaller build process completed successfully! Executable is located in ./dist"
exit 0