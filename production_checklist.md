# Production Deployment Checklist

## 🔧 Pre-Deployment Setup

### 1. Environment Configuration
- [ ] Copy `.env.production` to `.env` and fill in all values
- [ ] Set `FLASK_ENV=production`
- [ ] Generate secure `FLASK_SECRET` key
- [ ] Configure production database URL
- [ ] Set up Google OAuth credentials for production domain
- [ ] Configure email settings (Gmail app password)
- [ ] Set up Razorpay production keys
- [ ] Configure Dhan API credentials

### 2. Database Setup
- [ ] Create production PostgreSQL database
- [ ] Set up database user with proper permissions
- [ ] Configure SSL connection for database
- [ ] Run database migrations: `flask db upgrade`
- [ ] Set up database backups

### 3. Server Configuration
- [ ] Install Python 3.8+ on production server
- [ ] Install PostgreSQL client libraries
- [ ] Install Nginx
- [ ] Install SSL certificates (Let's Encrypt recommended)
- [ ] Configure firewall (ports 80, 443, 22)

## 🚀 Deployment Steps

### 1. Application Deployment
```bash
# Clone repository
git clone <your-repo-url>
cd calculatentrade

# Install dependencies
pip install -r requirements_production.txt

# Set environment variables
cp .env.production .env
# Edit .env with your production values

# Run deployment script
chmod +x deploy.sh
./deploy.sh
```

### 2. Nginx Configuration
```bash
# Copy nginx configuration
sudo cp nginx.conf /etc/nginx/sites-available/calculatentrade
sudo ln -s /etc/nginx/sites-available/calculatentrade /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. SSL Setup (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d calculatentrade.com -d www.calculatentrade.com
```

### 4. Process Management (Systemd)
Create `/etc/systemd/system/calculatentrade.service`:
```ini
[Unit]
Description=CalculatenTrade Gunicorn Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/calculatentrade
Environment="PATH=/path/to/calculatentrade/venv/bin"
ExecStart=/path/to/calculatentrade/venv/bin/gunicorn -c gunicorn_config.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable calculatentrade
sudo systemctl start calculatentrade
```

## 🔍 Post-Deployment Verification

### 1. Health Checks
- [ ] Application health: `curl https://calculatentrade.com/health`
- [ ] Database connectivity working
- [ ] SSL certificate valid
- [ ] All static files loading
- [ ] Email functionality working
- [ ] Payment gateway working
- [ ] OAuth login working

### 2. Performance Testing
- [ ] Load test with expected traffic
- [ ] Database query performance
- [ ] Memory usage monitoring
- [ ] Response time optimization

### 3. Security Verification
- [ ] SSL/TLS configuration (A+ rating on SSL Labs)
- [ ] Security headers present
- [ ] No debug information exposed
- [ ] Database credentials secure
- [ ] API keys properly configured

## 📊 Monitoring Setup

### 1. Application Monitoring
- [ ] Set up log rotation
- [ ] Configure error tracking (Sentry)
- [ ] Monitor application metrics
- [ ] Set up uptime monitoring

### 2. Database Monitoring
- [ ] Monitor connection pool usage
- [ ] Track slow queries
- [ ] Set up backup verification
- [ ] Monitor disk usage

### 3. Server Monitoring
- [ ] CPU and memory usage
- [ ] Disk space monitoring
- [ ] Network monitoring
- [ ] Security monitoring

## 🔄 Maintenance

### 1. Regular Tasks
- [ ] Database backups (daily)
- [ ] Log rotation and cleanup
- [ ] Security updates
- [ ] SSL certificate renewal
- [ ] Performance monitoring

### 2. Update Process
- [ ] Test updates in staging environment
- [ ] Database migration testing
- [ ] Rollback plan prepared
- [ ] Maintenance window scheduled

## 🚨 Emergency Procedures

### 1. Rollback Plan
- [ ] Previous version backup available
- [ ] Database rollback procedure
- [ ] DNS failover configured
- [ ] Emergency contact list

### 2. Incident Response
- [ ] Error notification system
- [ ] Escalation procedures
- [ ] Communication plan
- [ ] Post-incident review process

## 📞 Support Contacts

- Database Admin: [contact]
- System Admin: [contact]
- Development Team: [contact]
- Emergency Contact: [contact]