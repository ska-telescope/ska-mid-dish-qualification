#!/bin/bash

# Add your personal access token. DO NOT COMMIT IT TO THE REPO!
token=""
arch="arm64" # "universal2", "x86_64" or "arm64" 

# Check if token is set
if [ -z "$token" ]; then
    echo "ERROR: GitLab private token is not set."
    exit 1
fi

# Read version from .release file
if [ ! -f .release ]; then
    echo "ERROR: .release file not found."
    exit 1
fi

version=$(grep "^release=" .release | cut -d'=' -f2 | tr -d '[:space:]')

# Check if version was extracted
if [ -z "$version" ]; then
    echo "ERROR: Could not extract version from .release file."
    exit 1
fi

# Define variables for readability
file_path="./dist/DiSQ-$version-macos-$arch"
upload_url="https://gitlab.com/api/v4/projects/47618837/packages/generic/DiSQ-GUI/$version/DiSQ-$version-macos-$arch"

# Check if the file exists
if [ ! -f "$file_path" ]; then
    echo "ERROR: File '$file_path' not found."
    exit 1
fi

# Use curl to upload the file
echo "Uploading '$file_path' to GitLab package registry..."
response=$(curl --write-out '%{http_code}' --location \
    --header "PRIVATE-TOKEN: $token" \
    --upload-file "$file_path" \
    "$upload_url")

# Check response
if [ "$response" -eq 201 ]; then
    echo "Successfully uploaded '$file_path' to DiSQ package registry!"
    echo "See https://gitlab.com/ska-telescope/ska-mid-disq/-/packages/"
    exit 0
else
    echo "ERROR: Upload failed with status code $response."
    exit 1
fi
