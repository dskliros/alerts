# Production Deployment Guide

This guide walks you through deploying the Events Alerts application to your Ubuntu server using Docker Secrets for secure credential management.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Server Setup](#initial-server-setup)
3. [Secrets Configuration](#secrets-configuration)
4. [Deployment](#deployment)
5. [Verification](#verification)
6. [Maintenance](#maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Security Best Practices](#security-best-practices)

---

## Prerequisites

### On Your Ubuntu Server

1. **Docker Engine** (version 20.10 or higher)
   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   
   # Add your user to docker group
   sudo usermod -aG docker $USER
   
   # Log out and back in for group changes to take effect
   ```

2. **Docker Compose Plugin** (version 2.0 or higher)
   ```bash
   # Install Docker Compose
   sudo apt-get update
   sudo apt-get install docker-compose-plugin
   
   # Verify installation
   docker compose version
   ```

3. **Git** (for cloning the repository)
   ```bash
   sudo apt-get install git
   ```

4. **SSH Access** to your server with sudo privileges

### Required Files on Server

- SSH private keys for database tunnel
- Access to your database credentials
- SMTP server credentials
- Microsoft Teams webhook URL (if using Teams notifications)

---

## Initial Server Setup

### 1. Clone the Repository

```bash
# SSH into your Ubuntu server
ssh user@your-server-ip

# Clone the repository
cd /opt  # or your preferred location
sudo git clone https://github.com/your-org/your-repo.git events-alerts
cd events-alerts

# Set appropriate ownership
sudo chown -R $USER:$USER /opt/events-alerts
```

### 2. Copy SSH Keys to Server

On your **local machine** (Mac):

```bash
# Copy SSH keys to the server
scp ~/.ssh/prominence_user_key_rsa4096 user@your-server-ip:/home/user/.ssh/
scp ~/.ssh/datalab_prominence_prod.pem user@your-server-ip:/home/user/.ssh/

# Set appropriate permissions on the server
ssh user@your-server-ip "chmod 600 ~/.ssh/prominence_user_key_rsa4096 ~/.ssh/datalab_prominence_prod.pem"
```

### 3. Create Required Directories

```bash
cd /opt/events-alerts

# Create directories that should persist
mkdir -p logs data media queries

# Set appropriate permissions
chmod 755 logs data
```

---

## Secrets Configuration

### 1. Create Secrets File

On your Ubuntu server, create a `secrets.env` file with your actual credentials:

```bash
cd /opt/events-alerts

# Copy the template
cp secrets.env.template secrets.env

# Edit with your actual credentials
vim secrets.env  # or nano, if you prefer
```

**Important:** Fill in ALL the placeholder values with your actual credentials:
- Database credentials
- SSH tunnel credentials
- SMTP credentials
- Teams webhook URL
- Email recipient lists
- Paths to SSH key files

### 2. Secure the Secrets File

```bash
# Set restrictive permissions
chmod 600 secrets.env

# Verify only you can read it
ls -la secrets.env
# Should show: -rw------- 1 youruser youruser
```

### 3. Initialize Docker Secrets

Run the initialization script to create all Docker secrets:

```bash
# Make the script executable
chmod +x scripts/init_secrets.sh

# Run the initialization script
./scripts/init_secrets.sh
```

The script will:
- Initialize Docker Swarm (required for secrets)
- Read credentials from `secrets.env`
- Create all required Docker secrets
- Verify all secrets were created successfully

**Expected output:**
```
===========================================================
  Docker Secrets Initialization Script
===========================================================

✓ Docker is installed
✓ Docker Swarm is already active
✓ Secrets file found: /opt/events-alerts/secrets.env
✓ Secrets loaded from file

Creating Docker secrets...

✓ Created secret: ssh_host
✓ Created secret: ssh_port
...
✓ Created secret from file: ssh_key_content
✓ Created secret from file: ssh_ubuntu_key_content

===========================================================
  Created Secrets
===========================================================
ID                          NAME                            CREATED
...

✓ All required secrets are present!

===========================================================
  Docker Secrets initialized successfully!
===========================================================
```

### 4. Secure or Delete Secrets File

After successful initialization, you have two options:

**Option A: Delete the file** (recommended if you have credentials stored elsewhere)
```bash
shred -u secrets.env  # Securely delete
```

**Option B: Move to secure location**
```bash
# Move to your home directory with restricted permissions
mv secrets.env ~/secrets-backup.env
chmod 400 ~/secrets-backup.env
```

---

## Deployment

### 1. Build and Deploy the Application

```bash
cd /opt/events-alerts

# Deploy using production configuration
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

This command:
- Uses `docker-compose.yml` (base configuration)
- Overlays `docker-compose.prod.yml` (production settings with secrets)
- Builds the Docker image
- Starts the container in detached mode

### 2. Verify Deployment

```bash
# Check container status
docker compose ps

# Expected output:
# NAME         IMAGE              STATUS         PORTS
# alerts-app   events-alerts      Up X seconds

# Check logs
docker compose logs -f alerts

# Press Ctrl+C to stop following logs
```

### 3. Test Database Connection

```bash
# Run a connection test
docker compose exec alerts python -c "from src.db_utils import check_db_connection; print('Success!' if check_db_connection() else 'Failed!')"
```

---

## Verification

### Check Application Health

```bash
# View container health status
docker inspect alerts-app --format='{{.State.Health.Status}}'
# Should show: healthy

# View health check logs
docker inspect alerts-app --format='{{range .State.Health.Log}}{{.Output}}{{end}}'
```

### Monitor Logs

```bash
# Follow live logs
docker compose logs -f alerts

# View last 100 lines
docker compose logs --tail=100 alerts

# View logs for specific time range
docker compose logs --since 1h alerts
```

### Check Sent Events

```bash
# View the sent events tracking file
cat data/sent_events.json
```

### Verify Email Sending

Check your email to verify alerts are being sent, or check the logs for SMTP activity.

---

## Maintenance

### Update Application Code

```bash
cd /opt/events-alerts

# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# View logs to ensure successful restart
docker compose logs -f alerts
```

### Update SQL Queries

SQL queries are mounted as a volume, so you can update them without rebuilding:

```bash
cd /opt/events-alerts

# Edit query files
vim queries/EventHotWorksDetails.sql

# Restart container to pick up changes (graceful restart)
docker compose restart alerts
```

### Rotate Secrets

To update credentials (e.g., change database password):

```bash
cd /opt/events-alerts

# 1. Update your secrets.env file with new credentials
vim secrets.env

# 2. Remove old secrets
docker secret rm db_pass  # or whichever secret you're rotating

# 3. Recreate secrets (will skip existing ones)
./scripts/init_secrets.sh

# 4. Force recreate the container
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate
```

### View Container Resource Usage

```bash
# View resource statistics
docker stats alerts-app

# One-time snapshot
docker stats --no-stream alerts-app
```

### Backup Data

```bash
# Backup the data directory (contains sent_events.json)
cd /opt/events-alerts
tar -czf backup-data-$(date +%Y%m%d).tar.gz data/

# Backup logs
tar -czf backup-logs-$(date +%Y%m%d).tar.gz logs/
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check container logs
docker compose logs alerts

# Check if secrets are properly mounted
docker compose exec alerts ls -la /run/secrets/

# Verify secrets exist
docker secret ls
```

### Database Connection Issues

```bash
# Test database connection interactively
docker compose exec alerts python

# Then in Python:
from src.db_utils import check_db_connection
result = check_db_connection()
print(f"Connection successful: {result}")
```

### SSH Tunnel Issues

```bash
# Check if SSH keys are readable
docker compose exec alerts ls -la /tmp/ssh_*

# Verify SSH key permissions
docker compose exec alerts stat -c "%a %n" /tmp/ssh_*
# Should show: 400
```

### Secrets Not Found

```bash
# List all secrets
docker secret ls

# Inspect a specific secret (shows metadata, not content)
docker secret inspect ssh_host

# If secret is missing, recreate it
echo "your-value" | docker secret create secret_name -
```

### Application Not Sending Emails

```bash
# Check SMTP configuration in logs
docker compose logs alerts | grep -i smtp

# Test SMTP connection manually
docker compose exec alerts python

# Then in Python:
import smtplib
from decouple import config
server = smtplib.SMTP(config('SMTP_HOST'), config('SMTP_PORT'))
server.quit()
```

### View Environment Inside Container

```bash
# Check environment variables
docker compose exec alerts env | sort

# Check if secrets are accessible
docker compose exec alerts cat /run/secrets/db_host
```

---

## Security Best Practices

### 1. File Permissions

```bash
# Ensure restrictive permissions on sensitive files
chmod 600 secrets.env  # If keeping it
chmod 700 scripts/init_secrets.sh
chmod 600 ~/.ssh/prominence_user_key_rsa4096
chmod 600 ~/.ssh/datalab_prominence_prod.pem
```

### 2. Firewall Configuration

```bash
# Only allow necessary ports
sudo ufw allow 22/tcp  # SSH
sudo ufw enable

# Block direct database access from outside
sudo ufw deny 5432/tcp
```

### 3. Regular Updates

```bash
# Keep system updated
sudo apt-get update
sudo apt-get upgrade

# Update Docker
sudo apt-get install --only-upgrade docker-ce docker-ce-cli containerd.io
```

### 4. Secrets Rotation Schedule

- Database passwords: Every 90 days
- SMTP passwords: Every 90 days
- SSH keys: Every 180 days
- Teams webhooks: As needed

### 5. Audit Docker Secrets

```bash
# List all secrets with creation dates
docker secret ls --format "table {{.ID}}\t{{.Name}}\t{{.CreatedAt}}"

# Check which containers are using which secrets
docker ps --format "{{.Names}}" | xargs -I {} docker inspect {} --format='{{.Name}}: {{range .Config.Labels}}{{.}}{{end}}'
```

### 6. Monitor Logs for Security Events

```bash
# Watch for authentication failures
docker compose logs alerts | grep -i "failed\|error\|denied"

# Set up log rotation
# (Already configured via LOG_MAX_BYTES and LOG_BACKUP_COUNT)
```

---

## Advanced Configuration

### Enable Scheduled Execution

To run the alerts on a schedule (e.g., every hour):

1. Edit `docker-compose.prod.yml`
2. Uncomment and modify the `command` line:
   ```yaml
   command: sh -c "while true; do python src/events_alerts.py && sleep 3600; done"
   ```
3. Restart the container:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate
   ```

### Use Docker Stack Deploy (for multiple nodes)

If you need to deploy across multiple servers:

```bash
# Deploy as a stack
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml events-alerts

# Check stack services
docker stack services events-alerts

# Remove stack
docker stack rm events-alerts
```

---

## Quick Reference Commands

```bash
# Start application
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Stop application
docker compose down

# Restart application
docker compose restart alerts

# View logs
docker compose logs -f alerts

# Execute command in container
docker compose exec alerts <command>

# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Remove everything (including volumes)
docker compose down -v
```

---

## Support

For issues or questions:
1. Check the logs first: `docker compose logs alerts`
2. Review this documentation
3. Contact the development team
4. Check the project repository for updates

---

**Last Updated:** November 2025  
**Maintained by:** Prominence Maritime S.A. DevOps Team
