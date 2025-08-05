#!/usr/bin/env bash

# Update package lists
apt-get update

# Install only the required system packages for our application
apt-get install -y --no-install-recommends poppler-utils

# Clean up the apt cache to keep the image size small
rm -rf /var/lib/apt/lists/*