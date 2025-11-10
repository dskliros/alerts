# Events Alerts System

> **Note**: This system was developed for internal use at **Prominence Maritime** and **Seatraders**.
> It contains company-specific configuration and may require significant modifications for other use cases.

**Automated (currently, 7 Nov 2025, email only) notifications for events, defaulting to "Hot Work" Permit Events**

Monitors ORCA CORE DB for specific events (such as "hot work" permits) (configurable in `.env`) and automatically sends notifications to designated recipients (specified in `.env`). Runs continuously with configurable intervals (denoted by `SCHEDULE_FREQUENCY` in `.env`) and prevents duplicate notifications provided a certain number of days (denoted by `REMINDER_FREQUENCY_DAYS` in `.env`) has not passed.

---

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- ORCA Core (PostgreSQL) database access (configured in `.env`)
- SMTP email server credentials (configured in `.env`)
- SSH access if DB requires SSH Tunnel (configured in `.env`), but not necessary if run from within a remote linux server that has direct DB access

### 1. Clone & Setup

Note: currently, it is the `easy_prod` branch that is being used and updated, **not** `main`
```bash
git clone https://github.com/dskliros/alerts.git
cd events-alerts
```

### 2. Configure Environment

```bash
# All settings are specified in a `.env`. **Never commit `.env` to git/github.**
# Copy the example from .env.example and edit as necessary:
cp .env.example .env
vi .env
```

### 3. Add SSH Keys

Place private SSH keys in the user's .ssh folder, e.g. `/home/ubuntu/.ssh`,  or update paths in `docker-compose.yml`:
```yaml
volumes:
    - ~/.ssh/your_key.pem:/app/ssh_key:ro
    - ~/.ssh/your_ubuntu_key.pem:/app/ssh_ubuntu_key:ro
```

### 4. Run Locally (Dev)

```bash
# Build and run in foreground
docker compose up --build

# Build and run in background (detached mode)
docker compose up --build -d

# View logs (-f flag for continuously updated)
docker compose logs -f

# Stop
docker compose down
```

### 5. Deploy to Remote Server

```bash
# SSH into your server
ssh user@your-server

# Clone and Configure
cd /opt/events-alerts
git pull # or clone

# Set user permissions
echo UID=$(id -u)
echo GID=$(id -g)
# ... and place resulting values in .env

# Run in detached mode
docker compose up --build -d

# Autorestart enabled by default upon reboot
# specified in docker-compose.yml: restart: unless-stopped
```

---

## Project Structure
```
events-alerts/
├── .git
│   ├── branches
│   ├── hooks
│   ├── info
│   ├── logs
│   ├── objects
│   ├── refs
│   ├── COMMIT_EDITMSG
│   ├── FETCH_HEAD
│   ├── HEAD
│   ├── ORIG_HEAD
│   ├── config
│   ├── description
│   ├── index
│   └── packed-refs
├── data
│   └── sent_events.json                    # Tracking sent events
├── docs
│   ├── AlertDev.docx
│   └── example.pdf
├── logs
│   └── events_alerts.log                   # Application logs
├── media                                   # Email company logos
│   ├── logo_prominence_maritime_teliko_new_1.png
│   ├── trans-logo-blue.png
│   ├── trans_logo_prominence_procreate_small.png
│   ├── trans_logo_prominence_procreate_small_flipped.png
│   └── trans_logo_seatraders_procreate_small.png
├── queries
│   ├── EventHotWorksDetails.sql            # Main events query
│   ├── TypeAndStatus.sql                   # Type and status lookup
│   └── get_events_name.sql                 # Events name lookup
├── scripts
│   ├── email_checker.py                    # Verify STMP settings
│   └── verify_teams_webhook.py             # Verify Teams integration
├── src
│   ├── __init__.py
│   ├── db_utils.py                         # Database connection utilities
│   └── events_alerts.py                    # Main application logic
├── tests
│   ├── conftest.py                         # Pytest configuration
│   ├── run_tests.sh                        # Test runner script
│   └── test_*.py                           # Unit tests
├── .dockerignore
├── .env                                    # CONFIGURATION (DO NOT COMMIT)
├── .env.example                            # Configuration template
├── .gitignore
├── Dockerfile                              # Container definition
├── README.md                               # This file
├── docker-compose.yml                      # Docker configuration
├── pytest.ini
└── requirements.txt                        # Python dependencies
```

## Common Tasks

### Rebuild Container from Scratch

```bash
# Stop and remove containers
docker compose down

# Rebuild image from scratch
docker compose build --no-cache

# Start with new containers (-d in detached mode)
docker compose up -d
```

### Verify User and Group IDs

```bash
# These, 
echo id -u
echo id -g

# .. which are specified in .env and
# denoted by UID and GID should match with:
docker exec alerts-app id

# If they don't match, rebuild container from scratch (as specified above), 
# see also below.
```

### View logs

```bash
# Real-time logs
docker compose logs -f

# Last 100 lines
docker compose logs --tail 100

# Logs from specific timeframe
docker compose logs --since 30m
```

### Update config

```bash
# Edit .env
vi .env

# Restart to apply changes
docker compose up --force-recreate -d
```

### Check Status & Healthcheck

```bash
# View running containers
docker compose ps

# If Status is marked as unhealthy:
docker inspect --format='{{json .State.Health}}' alerts-app | jq

# Alternative container health check
docker ps -a
```

### Manual Testing

```bash
# Run test suite
docker compose run --rm alerts pytest

# Run a specific test
docker compose run -rm alerts pytest tests/test_tracking.py::test_load_sent_events_with_data -v
```

### Debugging

```bash
# Enter container shell
docker compose exec alerts /bin/bash

# Check environment variables, e.g.,
docker compose exec alerts env | grep DB_

# Test DB connection
docker compose exec alerts python -c "from src.db_utils import check_db_connection; print(check_db_connection())"
```

---

# Testing (currently only 59% coverage)

```bash
# With coverage report
docker compose run --rm alerts pytest --cov=src --cov-report=term-missing

# Verbose output
docker compose run --rm alerts pytest -v

# Stop on first failure
docker compose run --rm alerts pytest -x
```

---

## Licence

MIT

## Contributors

Dr D Skliros

---

**Last Updated**: 2025-11-06
**Version**: 1.0.0
