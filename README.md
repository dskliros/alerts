# Events Alerts System

**Automated email notifications for hot work permit events from PostgreSQL database.**

Monitor your database for specific events (hot work permits) and automatically send email notifications to designated recipients. Runs continuously with configurable intervals and prevents duplicate notifications.

---

## Quick Start

### Prerequisites
- Docker & Docker Compose installed
- PostgreSQL database access
- SMTP email server credentials
- SSH access (if database requires SSH tunnel)

### 1. Clone & Setup

```bash
git clone <repository-url>
cd events-alerts
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your credentials
vim .env  # or nano, code, etc.
```

### 3. Add SSH Keys (if using SSH tunnel)

Place your SSH private keys in the project root or update paths in `docker-compose.yml`:
```yaml
volumes:
  - ~/.ssh/your_key.pem:/app/ssh_key:ro
  - ~/.ssh/your_ubuntu_key.pem:/app/ssh_ubuntu_key:ro
```

### 4. Run Locally (Development)

```bash
# Build and run in foreground
docker compose up --build

# Run in background (detached mode)
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### 5. Deploy to Remote Server

```bash
# SSH into your server
ssh user@your-server

# Clone and configure
cd /opt/events-alerts
git pull  # or clone

# Set proper user permissions in .env
export UID=$(id -u)
export GID=$(id -g)

# Run in detached mode
docker compose up --build -d

# Enable auto-restart on reboot (optional)
# Add to docker-compose.yml: restart: unless-stopped
```

---

## Configuration

All settings are in `.env` file. **Never commit this file to git.**

### Essential Configuration

```bash
# ----------------------------------------------------------------
# Database Connection
# ----------------------------------------------------------------
DB_HOST=db_host.com
DB_PORT=5432
DB_NAME=db_name
DB_USER=db_user
DB_PASS=dp_pass

# ----------------------------------------------------------------
# SSH Tunnel (set to false if server is on same network as DB)
# ----------------------------------------------------------------
USE_SSH_TUNNEL=true
SSH_HOST=your-jump-host.com
SSH_PORT=22
SSH_USER=ubuntu
SSH_KEY_PATH=/app/ssh_key                   # Path inside container
SSH_UBUNTU_KEY_PATH=/app/ssh_ubuntu_key

# ----------------------------------------------------------------
# Email Configuration (SMTP)
# ----------------------------------------------------------------
SMTP_HOST=XX.XXX.XXX.XX
SMTP_PORT=465
SMTP_USER=user@seatraders.com
SMTP_PASS=XXXXXXXXXXXXXXXXXXXXXXXXX

# ----------------------------------------------------------------
# Email Recipients
# ----------------------------------------------------------------
INTERNAL_RECIPIENTS=user@mail.com,user2@mail.com
PROMINENCE_EMAIL_RECIPIENTS=user1@prominencemaritime.com,user3@prominencemaritime.com
SEATRADERS_EMAIL_RECIPIENTS=user2@seatraders.com

# ----------------------------------------------------------------
# Query Parameters
# ----------------------------------------------------------------
EVENT_TYPE_ID=18                    # Permits event type
EVENT_STATUS_ID=3                   # Closed status (3 = For Review)
EVENT_NAME_FILTER=hot               # Event name must contain "hot"
EVENT_EXCLUDE=vessel                # Exclude if event name contains "vessel"
EVENT_LOOKBACK_DAYS=4               # Search last 4 days

# ----------------------------------------------------------------
# Scheduler Settings
# ----------------------------------------------------------------
SCHEDULE_FREQUENCY=0.5          # Hours between checks (30 min) (floats allowed)
REMINDER_FREQUENCY_DAYS=3       # Resend after 3 days (floats allowed)

# ----------------------------------------------------------------
# Feature Flags
# ----------------------------------------------------------------
ENABLE_EMAIL_ALERTS=true
ENABLE_TEAMS_ALERTS=false
ENABLE_SPECIAL_TEAMS_EMAIL=false
```

---

## Project Structure

```
events-alerts/
├── src/
│   ├── events_alerts.py            # Main application logic
│   └── db_utils.py                 # Database connection utilities
├── queries/
│   ├── EventHotWork.sql            # Main event query
│   └──── TypeAndStatus.sql         # Event type/status lookup
├── tests/
│   ├── conftest.py                 # Pytest configuration
│   ├── test_*.py                   # Unit tests
│   └── run_tests.sh                # Test runner script
├── scripts/
│   ├── email_checker.py            # Verify SMTP settings
│   └── verify_teams_webhook.py     # Test Teams integration
├── media/                          # Email logos
├── data/
│   └── sent_events.json            # Tracking sent events
├── logs/
│   └── events_alerts.log           # Application logs
├── docker-compose.yml              # Docker configuration
├── Dockerfile                      # Container definition
├── requirements.txt                # Python dependencies
├── .env                            # Configuration (DO NOT COMMIT)
├── .env.example                    # Configuration template
└── README.md                       # This file
```

---

## Common Tasks

### View Logs

```bash
# Real-time logs
docker compose logs -f

# Last 100 lines
docker compose logs --tail 100

# Logs from specific timeframe
docker compose logs --since 30m
```

### Update Configuration

```bash
# Edit .env file
vi .env

# Restart to apply changes
docker compose up --force-recreate -d
```

### Check Status

```bash
# View running containers
docker compose ps

# Check container health
docker ps -a
```

### Manual Testing

```bash
# Test SMTP connection
docker compose run --rm alerts python scripts/email_checker.py

# Run test suite
docker compose run --rm alerts pytest

# Run specific test
docker compose run --rm alerts pytest tests/test_email_functions.py -v
```

### Debugging

```bash
# Enter container shell
docker compose exec alerts /bin/bash

# Check environment variables
docker compose exec alerts env | grep DB_

# Test database connection
docker compose exec alerts python -c "from src.db_utils import check_db_connection; print(check_db_connection())"
```

---

## Testing (not fully up-to-date)

### Run All Tests

```bash
# With coverage report
docker compose run --rm alerts pytest --cov=src --cov-report=term-missing

# Verbose output
docker compose run --rm alerts pytest -v

# Stop on first failure
docker compose run --rm alerts pytest -x
```

### Test Categories

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

---

## Troubleshooting

### Database Connection Issues

**Problem**: `Connection refused` or `timeout`

**Solutions**:
1. Verify `USE_SSH_TUNNEL` setting matches your network topology
2. Check SSH key paths in `docker-compose.yml`
3. Confirm database credentials in `.env`
4. Test connection: `docker compose exec alerts python -c "from src.db_utils import check_db_connection; print(check_db_connection())"`

### Email Not Sending

**Problem**: No emails received

**Solutions**:
1. Check `ENABLE_EMAIL_ALERTS=true` in `.env`
2. Verify SMTP credentials
3. Run: `docker compose run --rm alerts python scripts/email_checker.py`
4. Check logs: `docker compose logs | grep "Email sent"`

### Duplicate Emails

**Problem**: Receiving same notification repeatedly

**Solutions**:
1. Check `REMINDER_FREQUENCY_DAYS` - may be too short
2. Verify `data/sent_events.json` is being persisted (volume mount)
3. Ensure container user has write permissions to `data/` folder

### Container Exits Immediately

**Problem**: Container starts then stops

**Solutions**:
1. Check logs: `docker compose logs`
2. Verify `.env` file exists and is readable
3. Ensure all required environment variables are set
4. Check file permissions on mounted volumes

### No Events Found

**Problem**: Logs show "No events found matching criteria"

**Solutions**:
1. Verify query parameters in `.env`:
   - `EVENT_TYPE_ID` (18 = Permits)
   - `EVENT_STATUS_ID` (3 = For Review, 6 = Closed)
   - `EVENT_NAME_FILTER` and `EVENT_EXCLUDE`
2. Increase `EVENT_LOOKBACK_DAYS`
3. Test query directly in database client

---

## Security Best Practices

### DO:
- Keep `.env` file out of version control (already in `.gitignore`)
- Use SSH keys with proper permissions (`chmod 600`)
- Rotate SMTP passwords regularly
- Use app-specific passwords for Gmail
- Set `restart: unless-stopped` for production

### DO NOT:
- Commit `.env` or SSH keys to git
- Share SMTP credentials via insecure channels
- Use root user in containers (already using `${UID}:${GID}`)
- Disable SSL/TLS for SMTP connections

---

## Monitoring

### Key Metrics to Watch

```bash
# Events found per run
docker compose logs | grep "Construction Successful"

# Emails send
docker compose logs | grep "Email sent successfully"

# Tracking cleanup
docker compose logs | grep "Removed"

# Errors
docker compose logs | grep ERROR
```

### Log Locations

- **Application logs**: `logs/events_alerts.log`
- **Docker logs**: `docker compose logs`
- **Tracking data**: `data/sent_events.json`

---

## Deployment Workflow

### Local Development → Remote Production

```bash
# 1. Develop locally
docker compose up

# 2. Test changes (not fully up-to-date)
pytest tests/ -v

# OR

# Test changes (not fully up-to-date)
docker compose run alerts
>> pytest tests/ -v

# 3. Commit and push
git add .
git commit -m "Description of changes"
git push origin main

# 4. Deploy to server
ssh user@remote-server
cd /opt/events-alerts
git pull
docker compose up --build -d

# 5. Verify deployment
docker compose ps
docker compose logs --tail 50
```

---

## Modifying Queries

All SQL queries are in `queries/` directory. Modify as needed:

### Example: Change Event Criteria

**File**: `queries/EventHotWork.sql`

```sql
-- Original
WHERE type_id = :type_id
  AND LOWER(name) LIKE :name_filter

-- Modified (add status filter)
WHERE type_id = :type_id
  AND LOWER(name) LIKE :name_filter
  AND status_id = :status_id
```

After changes:
```bash
docker compose up --force-recreate -d
```

---

## Support

### Logs Analysis

```bash
# Get last hour of activity
docker compose logs --since 1h | grep -E "RUN STARTED|Email sent|ERROR"

# Count emails sent today
docker compose logs --since "$(date +%Y-%m-%d)" | grep -c "Email sent successfully"

# Find errors
docker compose logs | grep -i error | tail -20
```

### Health Check

```bash
# Quick status check
docker compose ps && \
docker compose logs --tail 5 && \
ls -lh data/sent_events.json
```

---

## License

MIT

## Contributors

Dr D Skliros

---

## Related Documentation

- [Docker Compose Docs](https://docs.docker.com/compose/)
- [PostgreSQL Connection Strings](https://www.postgresql.org/docs/current/libpq-connect.html)
- [Python Decouple](https://github.com/henriquebastos/python-decouple)
- [SQLAlchemy](https://docs.sqlalchemy.org/)

---

**Last Updated**: 2025-11-06  
**Version**: 1.0.0
