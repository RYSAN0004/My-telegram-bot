# 🚀 Production Deployment Guide
## Group Guardian Bot - Enterprise Grade Telegram Protection

This guide provides comprehensive instructions for deploying the Group Guardian Bot in production environments capable of handling 10,000+ groups with high performance and reliability.

## 📋 Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended)
- **RAM**: 4GB minimum, 8GB+ recommended for 10,000+ groups
- **CPU**: 2+ cores, 4+ cores recommended
- **Storage**: 10GB minimum, SSD recommended
- **Network**: Stable internet connection with low latency

### Required Dependencies
```bash
# Install Python 3.11+
sudo apt update
sudo apt install python3.11 python3.11-pip python3.11-venv

# Install system dependencies
sudo apt install build-essential libssl-dev libffi-dev
```

## 🔧 Environment Setup

### 1. Clone and Setup Project
```bash
# Clone the repository
git clone <your-repo-url>
cd telegram-protection-bot

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file with the following variables:

```env
# Telegram API Credentials (Required)
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/groupguardian
# For SQLite (development): sqlite:///bot_data.db

# Performance Settings
MAX_WORKERS=10
RATE_LIMIT_REQUESTS=30
RATE_LIMIT_WINDOW=60
FLOOD_THRESHOLD=5
FLOOD_WINDOW=10

# Security Settings
GBAN_ADMIN_CHAT_ID=your_admin_chat_id
OWNER_USER_ID=your_user_id
DEBUG_MODE=false

# Feature Toggles
ENABLE_ANTISPAM=true
ENABLE_GBAN=true
ENABLE_CAPTCHA=true
ENABLE_WELCOME=true
ENABLE_CONTENT_FILTER=true

# Logging Configuration
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=30
ENABLE_AUDIT_LOG=true

# Performance Optimization
CACHE_SIZE=1000
MESSAGE_CACHE_TTL=3600
USER_CACHE_TTL=1800
```

## 🗄️ Database Setup

### PostgreSQL (Recommended for Production)
```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE groupguardian;
CREATE USER botuser WITH ENCRYPTED PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE groupguardian TO botuser;
\q

# Update .env with PostgreSQL connection string
DATABASE_URL=postgresql://botuser:secure_password@localhost:5432/groupguardian
```

### Database Migration
```bash
# Run initial migrations
python migrate.py
```

## 🚀 Deployment Options

### Option 1: Systemd Service (Recommended)

Create `/etc/systemd/system/groupguardian.service`:
```ini
[Unit]
Description=Group Guardian Telegram Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=botuser
Group=botuser
WorkingDirectory=/home/botuser/telegram-protection-bot
Environment=PATH=/home/botuser/telegram-protection-bot/venv/bin
ExecStart=/home/botuser/telegram-protection-bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=groupguardian

# Resource limits for 10,000+ groups
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable groupguardian
sudo systemctl start groupguardian
sudo systemctl status groupguardian
```

### Option 2: Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python healthcheck.py

EXPOSE 8000

CMD ["python", "main.py"]
```

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  bot:
    build: .
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://botuser:password@db:5432/groupguardian
    env_file:
      - .env
    depends_on:
      - db
      - redis
    volumes:
      - ./logs:/app/logs
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2'
        reservations:
          memory: 1G
          cpus: '1'

  db:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_DB: groupguardian
      POSTGRES_USER: botuser
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1'

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl/certs

volumes:
  postgres_data:
  redis_data:
```

Deploy with Docker:
```bash
docker-compose up -d
docker-compose logs -f bot
```

## ⚡ Performance Optimization

### 1. Database Optimization
```sql
-- Create indexes for better performance
CREATE INDEX idx_user_roles_chat_user ON user_roles(chat_id, user_id);
CREATE INDEX idx_gban_entries_user_id ON gban_entries(user_id);
CREATE INDEX idx_moderation_logs_chat_id ON moderation_logs(chat_id);
CREATE INDEX idx_moderation_logs_timestamp ON moderation_logs(timestamp);
CREATE INDEX idx_anti_spam_user_id ON anti_spam_data(user_id);

-- Enable connection pooling in production
```

### 2. Redis Caching (Optional but Recommended)
```python
# Add to requirements.txt
redis==4.5.4
aioredis==2.0.1
```

Update configuration for Redis caching:
```env
REDIS_URL=redis://localhost:6379/0
ENABLE_REDIS_CACHE=true
CACHE_TTL=3600
```

### 3. Nginx Configuration for Webhooks
Create `nginx.conf`:
```nginx
events {
    worker_connections 1024;
}

http {
    upstream bot_backend {
        server bot:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;
        
        location / {
            proxy_pass http://bot_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

## 🔒 Security Best Practices

### 1. Firewall Configuration
```bash
# Configure UFW firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 5432/tcp  # PostgreSQL should not be publicly accessible
```

### 2. SSL/TLS Setup
```bash
# Install Certbot for Let's Encrypt
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com
```

### 3. Environment Security
```bash
# Secure the .env file
chmod 600 .env
chown botuser:botuser .env

# Create dedicated user
sudo useradd -m -s /bin/bash botuser
sudo usermod -aG sudo botuser
```

## 📊 Monitoring and Logging

### 1. Log Management
```bash
# Configure log rotation
sudo tee /etc/logrotate.d/groupguardian << EOF
/home/botuser/telegram-protection-bot/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 botuser botuser
    postrotate
        systemctl reload groupguardian
    endscript
}
EOF
```

### 2. Health Check Endpoint
Create `healthcheck.py`:
```python
#!/usr/bin/env python3
"""Health check script for the bot"""

import asyncio
import sys
from database import Database

async def health_check():
    try:
        db = Database()
        await db.initialize()
        
        # Test database connection
        cursor = await db.connection.execute("SELECT 1")
        result = await cursor.fetchone()
        
        if result[0] == 1:
            print("✅ Health check passed")
            return True
        else:
            print("❌ Database test failed")
            return False
            
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    finally:
        if 'db' in locals():
            await db.close()

if __name__ == "__main__":
    result = asyncio.run(health_check())
    sys.exit(0 if result else 1)
```

### 3. Monitoring with Prometheus (Optional)
```bash
# Add monitoring dependencies
pip install prometheus-client

# Create monitoring endpoint
python monitoring.py
```

## 🔄 Backup and Recovery

### 1. Database Backup Script
Create `backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/home/botuser/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="groupguardian"

# Create backup directory
mkdir -p $BACKUP_DIR

# PostgreSQL backup
pg_dump $DB_NAME > $BACKUP_DIR/groupguardian_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/groupguardian_$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: groupguardian_$DATE.sql.gz"
```

### 2. Automated Backup Cron
```bash
# Add to crontab
crontab -e

# Backup every 6 hours
0 */6 * * * /home/botuser/backup.sh
```

## 🚦 Load Testing and Scaling

### 1. Performance Testing
```python
# Create load_test.py for testing bot performance
import asyncio
import aiohttp
import time

async def test_bot_performance():
    """Test bot response times and throughput"""
    # Implement load testing logic
    pass
```

### 2. Horizontal Scaling
For handling 10,000+ groups, consider:

- **Database Read Replicas**: Use PostgreSQL read replicas for read-heavy operations
- **Redis Cluster**: Implement Redis clustering for caching
- **Load Balancing**: Use multiple bot instances behind a load balancer
- **Message Queue**: Implement message queuing for high-volume processing

### 3. Resource Monitoring
```bash
# Monitor system resources
htop
iotop
netstat -tuln
```

## 🔧 Troubleshooting

### Common Issues and Solutions

1. **Memory Usage High**
   ```bash
   # Monitor memory usage
   ps aux | grep python
   
   # Adjust cache settings in .env
   CACHE_SIZE=500
   MESSAGE_CACHE_TTL=1800
   ```

2. **Database Connection Issues**
   ```bash
   # Check PostgreSQL status
   sudo systemctl status postgresql
   
   # Check connections
   sudo -u postgres psql -c "SELECT * FROM pg_stat_activity;"
   ```

3. **Rate Limiting Issues**
   ```bash
   # Check bot logs for rate limit errors
   journalctl -u groupguardian -f
   
   # Adjust rate limits in code
   ```

4. **High CPU Usage**
   ```python
   # Profile the application
   python -m cProfile main.py
   ```

## 📈 Scaling for 10,000+ Groups

### Architecture Recommendations

1. **Microservices Architecture**
   - Separate services for different features (spam detection, welcome system, etc.)
   - Use message queues for inter-service communication

2. **Database Sharding**
   - Shard data by chat_id for better performance
   - Use connection pooling

3. **Caching Strategy**
   - Implement multi-level caching (Redis + in-memory)
   - Cache frequently accessed data (user roles, group settings)

4. **Async Optimization**
   - Use async/await for all I/O operations
   - Implement connection pooling for database and HTTP requests

## 🎯 Production Checklist

- [ ] Environment variables configured
- [ ] Database setup and optimized
- [ ] SSL/TLS certificates installed
- [ ] Firewall configured
- [ ] Monitoring and logging setup
- [ ] Backup strategy implemented
- [ ] Health checks configured
- [ ] Performance testing completed
- [ ] Security audit performed
- [ ] Documentation updated

## 🔄 Maintenance

### Daily Tasks
- Monitor logs for errors
- Check system resources
- Verify backup completion

### Weekly Tasks
- Review performance metrics
- Update dependencies (security patches)
- Clean up old logs and backups

### Monthly Tasks
- Security audit
- Performance optimization review
- Database maintenance (VACUUM, ANALYZE)

## 📞 Support

For production support and enterprise features:
- Email: support@groupguardian.bot
- Telegram: @GroupGuardianSupport
- Documentation: https://docs.groupguardian.bot

---

**Production deployment complete!** Your Group Guardian Bot is now ready to handle 10,000+ groups with enterprise-grade security and performance.