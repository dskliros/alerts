#!/bin/bash

##############################################################################
# init_secrets.sh
# 
# Initialize Docker Swarm and create Docker secrets for production deployment
# 
# Usage:
#   1. Copy this script to your Ubuntu server
#   2. Create a secrets.env file with your credentials (see format below)
#   3. Run: chmod +x init_secrets.sh
#   4. Run: ./init_secrets.sh
#
# IMPORTANT: 
# - This script requires a secrets.env file with your actual credentials
# - Never commit secrets.env to git!
# - Keep secrets.env in a secure location
##############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Secrets file location
SECRETS_FILE="${SECRETS_FILE:-$PROJECT_ROOT/secrets.env}"

echo -e "${BLUE}===========================================================${NC}"
echo -e "${BLUE}  Docker Secrets Initialization Script${NC}"
echo -e "${BLUE}===========================================================${NC}"
echo ""

##############################################################################
# Function: Check if Docker is installed
##############################################################################
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker is not installed${NC}"
        echo "Please install Docker first: https://docs.docker.com/engine/install/ubuntu/"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker is installed${NC}"
}

##############################################################################
# Function: Initialize Docker Swarm
##############################################################################
init_swarm() {
    if docker info 2>/dev/null | grep -q "Swarm: active"; then
        echo -e "${GREEN}✓ Docker Swarm is already active${NC}"
    else
        echo -e "${YELLOW}Initializing Docker Swarm...${NC}"
        docker swarm init
        echo -e "${GREEN}✓ Docker Swarm initialized${NC}"
    fi
}

##############################################################################
# Function: Check if secrets file exists
##############################################################################
check_secrets_file() {
    if [ ! -f "$SECRETS_FILE" ]; then
        echo -e "${RED}Error: Secrets file not found: $SECRETS_FILE${NC}"
        echo ""
        echo "Please create a secrets.env file with the following format:"
        echo ""
        cat <<'EOF'
# SSH Configuration
SSH_HOST=XX.XXX.XXX.XXX
SSH_PORT=22
SSH_USER=prominence

# Database Configuration
DB_HOST=host_name.rds.amazonaws.com
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_db_user
DB_PASS=your_secure_password

# SMTP Configuration
SMTP_HOST=XX.XXX.XXX.XX
SMTP_PORT=25
SMTP_USER=username@email.com
SMTP_PASS=your_smtp_password

# Teams Configuration
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
SPECIAL_TEAMS_EMAIL=channel@emea.teams.ms

# Email Recipients (comma-separated)
INTERNAL_RECIPIENTS=user1@email.com,user2@email.com
PROMINENCE_EMAIL_RECIPIENTS=user1@prominence.com,user2@prominence.com
SEATRADERS_EMAIL_RECIPIENTS=user1@seatraders.com,user2@seatraders.com

# SSH Key Paths (for reading content)
SSH_KEY_FILE=/path/to/prominence_user_key_rsa4096
SSH_UBUNTU_KEY_FILE=/path/to/datalab_prominence_prod.pem
EOF
        echo ""
        exit 1
    fi
    echo -e "${GREEN}✓ Secrets file found: $SECRETS_FILE${NC}"
}

##############################################################################
# Function: Load secrets from file
##############################################################################
load_secrets() {
    # Source the secrets file
    set -a  # Export all variables
    source "$SECRETS_FILE"
    set +a  # Stop exporting
    echo -e "${GREEN}✓ Secrets loaded from file${NC}"
}

##############################################################################
# Function: Create or update a Docker secret
##############################################################################
create_secret() {
    local secret_name=$1
    local secret_value=$2
    
    if [ -z "$secret_value" ]; then
        echo -e "${YELLOW}⚠ Skipping empty secret: $secret_name${NC}"
        return
    fi
    
    # Check if secret already exists
    if docker secret ls --format "{{.Name}}" | grep -q "^${secret_name}$"; then
        echo -e "${YELLOW}Secret '$secret_name' already exists - removing...${NC}"
        docker secret rm "$secret_name" 2>/dev/null || true
    fi
    
    # Create the secret
    echo "$secret_value" | docker secret create "$secret_name" - > /dev/null
    echo -e "${GREEN}✓ Created secret: $secret_name${NC}"
}

##############################################################################
# Function: Create secret from file
##############################################################################
create_secret_from_file() {
    local secret_name=$1
    local file_path=$2
    
    if [ ! -f "$file_path" ]; then
        echo -e "${RED}✗ SSH key file not found: $file_path${NC}"
        return 1
    fi
    
    # Check if secret already exists
    if docker secret ls --format "{{.Name}}" | grep -q "^${secret_name}$"; then
        echo -e "${YELLOW}Secret '$secret_name' already exists - removing...${NC}"
        docker secret rm "$secret_name" 2>/dev/null || true
    fi
    
    # Create the secret from file
    docker secret create "$secret_name" "$file_path" > /dev/null
    echo -e "${GREEN}✓ Created secret from file: $secret_name${NC}"
}

##############################################################################
# Function: Create all secrets
##############################################################################
create_all_secrets() {
    echo ""
    echo -e "${BLUE}Creating Docker secrets...${NC}"
    echo ""
    
    # SSH Secrets
    create_secret "ssh_host" "$SSH_HOST"
    create_secret "ssh_port" "$SSH_PORT"
    create_secret "ssh_user" "$SSH_USER"
    
    # Database Secrets
    create_secret "db_host" "$DB_HOST"
    create_secret "db_port" "$DB_PORT"
    create_secret "db_name" "$DB_NAME"
    create_secret "db_user" "$DB_USER"
    create_secret "db_pass" "$DB_PASS"
    
    # SMTP Secrets
    create_secret "smtp_host" "$SMTP_HOST"
    create_secret "smtp_port" "$SMTP_PORT"
    create_secret "smtp_user" "$SMTP_USER"
    create_secret "smtp_pass" "$SMTP_PASS"
    
    # Teams Secrets
    create_secret "teams_webhook_url" "$TEAMS_WEBHOOK_URL"
    
    # SSH Keys from files
    if [ -n "$SSH_KEY_FILE" ]; then
        create_secret_from_file "ssh_key_content" "$SSH_KEY_FILE"
    fi
    
    if [ -n "$SSH_UBUNTU_KEY_FILE" ]; then
        create_secret_from_file "ssh_ubuntu_key_content" "$SSH_UBUNTU_KEY_FILE"
    fi
}

##############################################################################
# Function: List created secrets
##############################################################################
list_secrets() {
    echo ""
    echo -e "${BLUE}===========================================================${NC}"
    echo -e "${BLUE}  Created Secrets${NC}"
    echo -e "${BLUE}===========================================================${NC}"
    docker secret ls
    echo ""
}

##############################################################################
# Function: Verify secrets
##############################################################################
verify_secrets() {
    echo ""
    echo -e "${BLUE}Verifying secrets...${NC}"
    
    local required_secrets=(
        "ssh_host"
        "ssh_port"
        "ssh_user"
        "db_host"
        "db_port"
        "db_name"
        "db_user"
        "db_pass"
        "smtp_host"
        "smtp_port"
        "smtp_user"
        "smtp_pass"
        "teams_webhook_url"
        "ssh_key_content"
        "ssh_ubuntu_key_content"
    )
    
    local missing_secrets=()
    
    for secret in "${required_secrets[@]}"; do
        if docker secret ls --format "{{.Name}}" | grep -q "^${secret}$"; then
            echo -e "${GREEN}✓ $secret${NC}"
        else
            echo -e "${RED}✗ $secret${NC}"
            missing_secrets+=("$secret")
        fi
    done
    
    if [ ${#missing_secrets[@]} -eq 0 ]; then
        echo -e "${GREEN}All required secrets are present!${NC}"
        return 0
    else
        echo -e "${RED}Missing secrets: ${missing_secrets[*]}${NC}"
        return 1
    fi
}

##############################################################################
# Main execution
##############################################################################
main() {
    check_docker
    init_swarm
    check_secrets_file
    load_secrets
    create_all_secrets
    list_secrets
    verify_secrets
    
    echo ""
    echo -e "${GREEN}===========================================================${NC}"
    echo -e "${GREEN}  Docker Secrets initialized successfully!${NC}"
    echo -e "${GREEN}===========================================================${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Deploy your application:"
    echo "     docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
    echo ""
    echo "  2. Check application logs:"
    echo "     docker-compose logs -f alerts"
    echo ""
    echo "  3. Verify the application is running:"
    echo "     docker-compose ps"
    echo ""
}

# Run main function
main
