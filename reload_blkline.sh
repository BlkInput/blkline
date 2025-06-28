#!/usr/bin/env bash

# --- CONFIGURE THESE PATHS TO YOUR ENVIRONMENT ---
BOT_DIR="/root/blkline"        # <- where blkline.py lives
SERVICE_NAME="blkline.service" # <- your systemd unit name

cd "$BOT_DIR" || { echo "❌ Cannot cd to $BOT_DIR"; exit 1; }

echo "🔍 Checking for uncommitted changes…"
if [[ -n $(git status --porcelain) ]]; then
  echo "⚠️  Uncommitted changes detected; stashing…"
  git stash push -m "auto-stash before pull"
else
  echo "✅ Working tree clean."
fi

echo "🔄 Fetching latest from origin/main…"
git fetch origin main

echo "🔀 Resetting to origin/main…"
git reset --hard origin/main

echo "📦 Installing/updating dependencies…"
pip install -r requirements.txt

echo "🚀 Restarting $SERVICE_NAME…"
systemctl restart "$SERVICE_NAME"

echo "✅ Reload complete."
