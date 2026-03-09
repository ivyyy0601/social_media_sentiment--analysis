#!/bin/bash
# Render deployment start script - Single service fullstack deployment
# This script configures production settings for Render deployment

# Exit on error
set -e

echo "========================================="
echo "Building Frontend..."
echo "========================================="

# Build the React frontend
cd frontend

# Install ALL dependencies including devDependencies (needed for vite)
npm install --include=dev

# Build with production API base URL (same server for SPA)
# URLs in App.jsx already include /api/v1/, so just use root
export VITE_API_BASE=""
npx vite build

# Return to root
cd ..

echo "========================================="
echo "Setting up Backend..."
echo "========================================="

# Change to backend directory
cd backend

# Install Python dependencies (Render typically does this, but included for safety)
pip install -r requirements.txt

# Run database migrations
echo "Running database migrations..."
python3 migrations.py

# Set production environment variables
export FLASK_DEBUG=false
export FLASK_ENV=production

# Get the PORT from Render (defaults to 5000 if not set)
PORT=${PORT:-5000}

echo "========================================="
echo "Starting Flask app on port $PORT..."
echo "========================================="

# Start the app with gunicorn (production WSGI server)
# 4 workers, bind to 0.0.0.0 on the Render-provided PORT
gunicorn -w 4 -b 0.0.0.0:$PORT app:app
