# Deployment Guide

## Option 1: Render (Free)
1. Push code to GitHub
2. Connect to render.com
3. Set environment variables in Render dashboard
4. Deploy automatically

## Option 2: Railway (Free)
1. Push to GitHub
2. Connect to railway.app
3. Set env vars
4. Deploy

## Option 3: VPS/Server
```bash
# Install dependencies
sudo apt update
sudo apt install python3-pip nginx

# Clone and setup
git clone your-repo
cd CNT
pip install -r requirements.txt

# Run with Gunicorn
gunicorn --bind 0.0.0.0:5000 app:app
```

## Environment Variables Needed:
- FLASK_SECRET
- MAIL_USERNAME
- MAIL_PASSWORD
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET
- DATABASE_TYPE=sqlite