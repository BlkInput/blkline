#!/bin/bash

cd /root/beebo || exit

echo "📦 Checking for uncommitted changes..."

if [[ -n $(git status --porcelain) ]]; then
  echo "📝 Uncommitted changes found. Committing as WIP..."
  git add .
  git commit -m "WIP: auto-commit before pull"
else
  echo "✅ Working tree clean."
fi

echo "🔄 Pulling latest code from GitHub..."
git pull origin main

echo "🚀 Restarting Beebo service..."
systemctl restart beebo.service
