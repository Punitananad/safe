#!/bin/bash

# Production deployment script for CalculatenTrade
set -e

echo "🚀 Starting CalculatenTrade production deployment..."

# Create necessary directories
mkdir -p logs
mkdir -p uploads/mistakes
mkdir -p instance

# Set production environment
export FLASK_ENV=production
export FLASK_APP=app.py

# Install production dependencies
echo "📦 Installing production dependencies..."
pip install -r requirements_production.txt

# Database migrations
echo "🗄️ Running database migrations..."
flask db upgrade

# Create log files
touch logs/access.log
touch logs/error.log
touch logs/calculatentrade.log

# Set proper permissions
chmod 755 logs
chmod 644 logs/*.log
chmod 755 uploads
chmod 755 uploads/mistakes

# Stop existing Gunicorn processes
echo "🛑 Stopping existing processes..."
pkill -f gunicorn || true

# Start Gunicorn with production config
echo "🔥 Starting Gunicorn server..."
gunicorn -c gunicorn_config.py app:app &

# Wait for server to start
sleep 5

# Check if server is running
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Server started successfully!"
    echo "🌐 Application is running on http://localhost:8000"
    echo "📊 Health check: http://localhost:8000/health"
else
    echo "❌ Server failed to start. Check logs/error.log for details."
    exit 1
fi

echo "🎉 Deployment completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Configure Nginx with the provided nginx.conf"
echo "2. Set up SSL certificates"
echo "3. Configure your domain DNS"
echo "4. Set up monitoring and backups"