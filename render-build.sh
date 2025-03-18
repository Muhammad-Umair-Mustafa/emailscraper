#!/usr/bin/env bash

# Install Chromium
apt-get update
apt-get install -y chromium-browser

# Install dependencies
pip install -r requirements.txt
