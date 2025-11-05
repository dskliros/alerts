# README.md

## Summary
Successfully migrated from .env file configuration to Docker Secrets for
secure production deployment on Ubuntu server. Application now runs in
Docker Swarm mode with encrypted credential storage while maintaining
easy configuration management through .env.prod file.

## Migration Overview

### Security Improvements
- 15 credentials now stored as encrypted Docker Secrets
- SSH keys stored as secrets (not volume mounts)
- No credentials in environment variables or Docker images
- Credentials isolated per service using Docker Swarm

### Configuration Management
- Separated secrets (credentials) from configuration (settings)
- Email addresses moved to .env.prod for easy modification
- Query parameters, scheduler settings in .env.prod
- No secrets regeneration needed for config changes

### Deployment Architecture
- Docker Swarm mode for secrets support
- Stack deployment (not docker-compose)
- Direct database connection (SSH tunnel disabled on server)
- Persistent volumes for logs and data

## Changes Made

### New Files
- src/secrets_utils.py: Unified config loader (Docker Secrets + .env)
- docker-compose.prod.yml: Production stack configuration
- scripts/init_secrets.sh: Bash secrets initialization
- scripts/init_secrets.zsh: Zsh secrets initialization  
- .env.prod: Production configuration (non-secret settings)
- .env.test: Test environment for pytest
- docs/DEPLOYMENT.md: Production deployment guide

### Modified Files
- src/db_utils.py: Uses secrets_utils.get_config()
- src/events_alerts.py: Uses secrets_utils.get_config()
- tests/conftest.py: Loads .env.test for testing
- docker-compose.yml: Removed Mac-specific SSH key volume mounts
- .gitignore: Added secrets patterns

### Configuration Split
**Docker Secrets (15 total - rarely change):**
- SSH: ssh_host, ssh_port, ssh_user, ssh_key_content, ssh_ubuntu_key_content
- Database: db_host, db_port, db_name, db_user, db_pass
- SMTP: smtp_host, smtp_port, smtp_user, smtp_pass
- Teams: teams_webhook_url

**.env.prod (Configuration - change frequently):**
- Email recipients (internal, prominence, seatraders)
- Query parameters (EVENT_TYPE_ID, EVENT_STATUS_ID, filters)
- Scheduler settings (SCHEDULE_FREQUENCY, REMINDER_FREQUENCY_DAYS)
- Styling (COMPANY_NAME, logos, colors)
- Feature flags (ENABLE_EMAIL_ALERTS, ENABLE_TEAMS_ALERTS)

## Production Deployment Commands

### Initial Deployment (One-Time Setup)
```bash
# On Ubuntu server
cd /opt/events-alerts

# 1. Pull latest code
git pull origin main

# 2. Create secrets.env (credentials only)
cp secrets.env.template secrets.env
vim secrets.env  # Fill in actual credentials

# 3. Edit .env.prod (configuration)
vim .env.prod
# Set: USE_SSH_TUNNEL=false (on server, no tunnel needed)
# Set: Email recipients, query parameters, etc.

# 4. Ensure directories exist
mkdir -p logs data queries media

# 5. Initialize Docker Secrets
chmod +x scripts/init_secrets.sh
./scripts/init_secrets.sh
# Creates 15 Docker Secrets in Docker Swarm

# 6. (Optional) Delete secrets.env after initialization
shred -u secrets.env

# 7. Build Docker image
docker build -t events-alerts:latest .

# 8. Deploy stack
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml events-alerts
```

## Essential Management Commands

### Service Control
```bash
# Start/Deploy service
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml events-alerts

# Stop service
docker stack rm events-alerts

# Restart service (redeploy)
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml events-alerts

# Force update (useful after config changes)
docker service update --force events-alerts_alerts
```

### Monitoring & Logs
```bash
# View service status
docker stack services events-alerts
# Shows: ID, NAME, MODE, REPLICAS (should be 1/1), IMAGE

# Check running containers
docker ps
# Shows actual running containers

# Follow live logs (recommended for monitoring)
docker service logs -f events-alerts_alerts
# Press Ctrl+C to stop following

# View last 50 log lines
docker service logs --tail=50 events-alerts_alerts

# View logs since 1 hour ago
docker service logs --since 1h events-alerts_alerts

# Search logs for errors
docker service logs events-alerts_alerts | grep -i error

# View logs on disk
tail -f /opt/events-alerts/logs/events_alerts.log

# Check sent events tracking
cat /opt/events-alerts/data/sent_events.json
```

### Service Inspection
```bash
# Detailed service status
docker service ps events-alerts_alerts

# Service details (formatted)
docker service inspect events-alerts_alerts --pretty

# Check if tasks are running/failed
docker service ps events-alerts_alerts --no-trunc

# Resource usage
docker stats $(docker ps -q --filter name=events-alerts)
```

### Secrets Management
```bash
# List all secrets
docker secret ls

# Count secrets (should be 15)
docker secret ls | tail -n +2 | wc -l

# Inspect secret metadata (doesn't show content)
docker secret inspect ssh_host

# View which services use which secrets
docker service inspect events-alerts_alerts | grep -A 20 Secrets
```

## Configuration Change Procedures

### Procedure 1: Changing Non-Secret Configuration
**Use this for: Email recipients, query parameters, scheduler settings, styling**

```bash
# 1. SSH to server
ssh datalab

# 2. Navigate to project
cd /opt/events-alerts

# 3. Edit configuration
vim .env.prod

# Example changes:
# - Change email recipients:
#   INTERNAL_RECIPIENTS=new@email.com,another@email.com
#
# - Adjust query parameters:
#   EVENT_TYPE_ID=20
#   EVENT_STATUS_ID=7
#   EVENT_LOOKBACK_DAYS=500
#
# - Change scheduler frequency:
#   SCHEDULE_FREQUENCY=1.0  # Every hour instead of 28 seconds
#
# - Enable Teams alerts:
#   ENABLE_TEAMS_ALERTS=true

# 4. Save and exit (:wq in vim)

# 5. Redeploy stack (picks up new config)
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml events-alerts

# 6. Verify changes took effect
docker service logs --tail=20 events-alerts_alerts
# Check logs show new settings

# Total time: ~2 minutes
```

### Procedure 2: Rotating Credentials (Rare)
**Use this for: Database password, SMTP password, SSH keys, Teams webhook**

```bash
# 1. SSH to server
ssh datalab
cd /opt/events-alerts

# 2. Create/edit secrets.env with new credentials
vim secrets.env
# Update only the credential(s) that changed
# Example: DB_PASS=new_password_here

# 3. Remove old secret(s)
docker secret rm db_pass

# 4. Recreate secret(s)
echo "new_password_here" | docker secret create db_pass -

# Alternative: Re-run init script (recreates all secrets)
./scripts/init_secrets.sh

# 5. Force service recreation (to use new secrets)
docker service update --force events-alerts_alerts
# OR
docker stack rm events-alerts
sleep 5
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml events-alerts

# 6. Delete secrets.env
shred -u secrets.env

# 7. Verify
docker service logs --tail=50 events-alerts_alerts

# Total time: ~5 minutes
```

### Procedure 3: Updating Application Code
**Use this for: Code changes, bug fixes, new features**

```bash
# 1. SSH to server
ssh datalab
cd /opt/events-alerts

# 2. Pull latest code
git pull origin main

# 3. Rebuild Docker image
docker build -t events-alerts:latest .

# 4. Redeploy with new image
docker service update --image events-alerts:latest events-alerts_alerts
# OR
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml events-alerts

# 5. Monitor deployment
docker service logs -f events-alerts_alerts

# Total time: ~3-5 minutes (depending on build time)
```

### Procedure 4: Updating SQL Queries
**Use this for: Modifying query logic without code changes**

```bash
# 1. SSH to server
ssh datalab
cd /opt/events-alerts

# 2. Edit SQL file
vim queries/EventHotWorksDetails.sql
# Make your changes

# 3. Restart service (picks up new query)
docker service update --force events-alerts_alerts

# 4. Verify
docker service logs --tail=20 events-alerts_alerts

# Total time: ~1 minute
```

## Troubleshooting Commands

### Service Won't Start
```bash
# Check why service is failing
docker service ps events-alerts_alerts --no-trunc

# Check service events
docker service inspect events-alerts_alerts | grep -A 50 Events

# Check if secrets are accessible
docker service inspect events-alerts_alerts | grep -A 20 Secrets

# Verify secrets exist
docker secret ls | grep -E "(db_|smtp_|ssh_)"
```

### Database Connection Issues
```bash
# View connection errors
docker service logs events-alerts_alerts | grep -i "connection\|error"

# Test database credentials (from container)
docker exec -it $(docker ps -q --filter name=events-alerts) python -c \
  "from src.db_utils import check_db_connection; print(check_db_connection())"

# Check if USE_SSH_TUNNEL setting is correct
grep USE_SSH_TUNNEL /opt/events-alerts/.env.prod
# Should be: USE_SSH_TUNNEL=false (on server)
```

### Application Crashes/Errors
```bash
# View full error trace
docker service logs events-alerts_alerts | grep -A 50 -i "error\|exception\|traceback"

# Check container exit code
docker service ps events-alerts_alerts

# Inspect container that crashed
docker service ps events-alerts_alerts --no-trunc | head -2
```

### Performance Issues
```bash
# Check resource usage
docker stats $(docker ps -q --filter name=events-alerts)

# Check if scheduler is running too frequently
docker service logs --tail=10 events-alerts_alerts | grep "Sleeping for"

# Verify event query performance
docker service logs events-alerts_alerts | grep "Construction Successful"
# Check how long queries take
```

## Quick Reference Card

### Daily Operations
```bash
# Check if running
docker stack services events-alerts

# View recent activity  
docker service logs --tail=50 events-alerts_alerts

# Check for errors
docker service logs events-alerts_alerts | grep -i error
```

### Weekly Maintenance
```bash
# Check disk usage
du -sh /opt/events-alerts/logs
du -sh /opt/events-alerts/data

# Verify sent events tracking
wc -l /opt/events-alerts/data/sent_events.json

# Check log rotation working
ls -lh /opt/events-alerts/logs/
```

### Configuration Changes (Most Common)
```bash
# Change any setting in .env.prod
vim /opt/events-alerts/.env.prod
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml events-alerts
docker service logs --tail=20 events-alerts_alerts
```

## File Locations

### On Ubuntu Server (/opt/events-alerts/)
```
├── .env.prod              # Edit for config changes
├── data/
│   └── sent_events.json   # Event tracking
├── logs/
│   └── events_alerts.log  # Application logs
├── queries/               # SQL files (editable)
├── media/                 # Logo files
├── docker-compose.yml     # Base config (rarely edit)
├── docker-compose.prod.yml # Production config (rarely edit)
└── scripts/
    ├── init_secrets.sh    # Secrets initialization
    └── init_secrets.zsh   # Zsh version
```

### Important Files NOT on Server
- secrets.env: Only exists during setup, then deleted
- .env: Local development only (your Mac)
- docker-compose.override.yml: Local development only

## Testing

### Local Development (Mac)
```bash
# All tests pass
pytest tests -v  # 41 passed

# Docker works locally
docker compose up --build

# Uses .env file automatically
```

### Production (Ubuntu)
```bash
# Service running
docker stack services events-alerts  # 1/1 replicas

# Database connected
docker service logs events-alerts_alerts | grep "Connection Successful"

# Scheduler active
docker service logs events-alerts_alerts | grep "Scheduler Started"
```

## Performance Metrics

- **Startup time**: ~2-3 seconds
- **Database query time**: ~0.3 seconds
- **Run cycle**: ~3-4 seconds total
- **Check frequency**: Every 28 seconds (configurable)
- **Resource usage**: <512MB memory, <0.5 CPU

## Security Notes

- All 15 credentials encrypted in Docker Secrets
- Secrets only accessible to the service container
- SSH keys have 0400 permissions in secrets
- No credentials in Docker images or environment variables
- .env.prod contains no secrets (safe to version control)
- secrets.env deleted after initialization

## Backup Procedures

### Backup Data
```bash
# Backup sent events
cp /opt/events-alerts/data/sent_events.json \
   /opt/events-alerts/data/sent_events.json.backup.$(date +%Y%m%d)

# Backup logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz \
   /opt/events-alerts/logs/
```

### Backup Secrets (Store Securely)
```bash
# If you kept secrets.env in secure location
# Store in password manager or secure vault
# DO NOT commit to git
```

## Rollback Procedures

### Rollback Code
```bash
# Revert to previous git commit
git log --oneline  # Find commit hash
git checkout <previous-commit-hash>
docker build -t events-alerts:latest .
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml events-alerts
```

### Rollback Configuration
```bash
# Revert .env.prod changes
git checkout .env.prod
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml events-alerts
```

## Support & Documentation

- Full deployment guide: docs/DEPLOYMENT.md
- Configuration management: outputs/CONFIG_MANAGEMENT.md
- Email configuration: outputs/EMAIL_CONFIG_SIMPLIFIED.md
- Test fixes: outputs/TEST_FIX_GUIDE.md

## Production Verification Checklist

- [x] Docker Swarm initialized
- [x] 15 Docker Secrets created and verified
- [x] Image built: events-alerts:latest
- [x] Stack deployed: events-alerts
- [x] Service running: 1/1 replicas
- [x] Database connection: Successful
- [x] Scheduler active: Every 28 seconds
- [x] Logs persisting: /opt/events-alerts/logs/
- [x] Data persisting: /opt/events-alerts/data/
- [x] Configuration manageable: .env.prod
- [x] Email addresses editable without secrets regeneration

## Breaking Changes

None - Full backward compatibility maintained for local development

## Migration Path

- Local development: Unchanged (uses .env via docker-compose)
- Production: New (uses Docker Secrets via docker stack)
- Testing: Enhanced (uses .env.test automatically)

## Contributors

- Migration implemented: November 2025
- Deployed to: datalab-prominence-prod Ubuntu server
- Docker Swarm node: k5hha0wwn7defmkp4qc7r7i9l

---

**Status**: [OK] Production deployment successful
**Service**: events-alerts_alerts
**Replicas**: 1/1 healthy
**Last updated**: 2025-11-05
