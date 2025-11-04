#!/usr/bin/env zsh

##############################################################################
# init_secrets.zsh
# 
# Zsh-native version of Docker Secrets initialization script
# Uses zsh arrays and features for better performance
# 
# Usage: ./init_secrets.zsh
##############################################################################

setopt ERR_EXIT  # Exit on error (like bash's set -e)
setopt NO_UNSET  # Error on undefined variables

# Colors using zsh color module
autoload -U colors && colors

# Script directory (zsh-specific)
SCRIPT_DIR=${0:A:h}
PROJECT_ROOT=${SCRIPT_DIR:h}

# Secrets file location
SECRETS_FILE=${SECRETS_FILE:-$PROJECT_ROOT/secrets.env}

print -P "%F{blue}===========================================================%f"
print -P "%F{blue}  Docker Secrets Initialization Script (Zsh)%f"
print -P "%F{blue}===========================================================%f"
print ""

##############################################################################
# Function: Check if Docker is installed
##############################################################################
check_docker() {
    if ! command -v docker &>/dev/null; then
        print -P "%F{red}Error: Docker is not installed%f"
        print "Please install Docker first: https://docs.docker.com/engine/install/ubuntu/"
        exit 1
    fi
    print -P "%F{green}✓ Docker is installed%f"
}

##############################################################################
# Function: Initialize Docker Swarm
##############################################################################
init_swarm() {
    if docker info 2>/dev/null | grep -q "Swarm: active"; then
        print -P "%F{green}✓ Docker Swarm is already active%f"
    else
        print -P "%F{yellow}Initializing Docker Swarm...%f"
        docker swarm init
        print -P "%F{green}✓ Docker Swarm initialized%f"
    fi
}

##############################################################################
# Function: Check if secrets file exists
##############################################################################
check_secrets_file() {
    if [[ ! -f "$SECRETS_FILE" ]]; then
        print -P "%F{red}Error: Secrets file not found: $SECRETS_FILE%f"
        print ""
        print "Please create a secrets.env file with the following format:"
        print ""
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

# SSH Key Paths
SSH_KEY_FILE=/path/to/prominence_user_key_rsa4096
SSH_UBUNTU_KEY_FILE=/path/to/datalab_prominence_prod.pem
EOF
        print ""
        exit 1
    fi
    print -P "%F{green}✓ Secrets file found: $SECRETS_FILE%f"
}

##############################################################################
# Function: Load secrets from file (zsh-native)
##############################################################################
load_secrets() {
    # Use zsh parameter expansion to load .env file
    typeset -A secrets
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        
        # Remove leading/trailing whitespace
        key=${key## }
        key=${key%% }
        value=${value## }
        value=${value%% }
        
        # Export for use in functions
        export $key="$value"
    done < "$SECRETS_FILE"
    
    print -P "%F{green}✓ Secrets loaded from file%f"
}

##############################################################################
# Function: Create or update a Docker secret
##############################################################################
create_secret() {
    local secret_name=$1
    local secret_value=$2
    
    if [[ -z "$secret_value" ]]; then
        print -P "%F{yellow}⚠ Skipping empty secret: $secret_name%f"
        return 0
    fi
    
    # Check if secret already exists (zsh-native array handling)
    if docker secret ls --format "{{.Name}}" | grep -q "^${secret_name}$"; then
        print -P "%F{yellow}Secret '$secret_name' already exists - removing...%f"
        docker secret rm "$secret_name" 2>/dev/null || true
    fi
    
    # Create the secret
    print -n "$secret_value" | docker secret create "$secret_name" - >/dev/null
    print -P "%F{green}✓ Created secret: $secret_name%f"
}

##############################################################################
# Function: Create secret from file
##############################################################################
create_secret_from_file() {
    local secret_name=$1
    local file_path=$2
    
    if [[ ! -f "$file_path" ]]; then
        print -P "%F{red}✗ SSH key file not found: $file_path%f"
        return 1
    fi
    
    # Check if secret already exists
    if docker secret ls --format "{{.Name}}" | grep -q "^${secret_name}$"; then
        print -P "%F{yellow}Secret '$secret_name' already exists - removing...%f"
        docker secret rm "$secret_name" 2>/dev/null || true
    fi
    
    # Create the secret from file
    docker secret create "$secret_name" "$file_path" >/dev/null
    print -P "%F{green}✓ Created secret from file: $secret_name%f"
}

##############################################################################
# Function: Create all secrets (using zsh arrays)
##############################################################################
create_all_secrets() {
    print ""
    print -P "%F{blue}Creating Docker secrets...%f"
    print ""
    
    # Define secret mappings using zsh associative array
    typeset -A secret_map=(
        ssh_host "$SSH_HOST"
        ssh_port "$SSH_PORT"
        ssh_user "$SSH_USER"
        db_host "$DB_HOST"
        db_port "$DB_PORT"
        db_name "$DB_NAME"
        db_user "$DB_USER"
        db_pass "$DB_PASS"
        smtp_host "$SMTP_HOST"
        smtp_port "$SMTP_PORT"
        smtp_user "$SMTP_USER"
        smtp_pass "$SMTP_PASS"
        teams_webhook_url "$TEAMS_WEBHOOK_URL"
        special_teams_email "$SPECIAL_TEAMS_EMAIL"
        internal_recipients "$INTERNAL_RECIPIENTS"
        prominence_email_recipients "$PROMINENCE_EMAIL_RECIPIENTS"
        seatraders_email_recipients "$SEATRADERS_EMAIL_RECIPIENTS"
    )
    
    # Create secrets from array
    for secret_name secret_value in ${(kv)secret_map}; do
        create_secret "$secret_name" "$secret_value"
    done
    
    # SSH Keys from files
    if [[ -n "$SSH_KEY_FILE" ]]; then
        create_secret_from_file "ssh_key_content" "$SSH_KEY_FILE"
    fi
    
    if [[ -n "$SSH_UBUNTU_KEY_FILE" ]]; then
        create_secret_from_file "ssh_ubuntu_key_content" "$SSH_UBUNTU_KEY_FILE"
    fi
}

##############################################################################
# Function: List created secrets
##############################################################################
list_secrets() {
    print ""
    print -P "%F{blue}===========================================================%f"
    print -P "%F{blue}  Created Secrets%f"
    print -P "%F{blue}===========================================================%f"
    docker secret ls
    print ""
}

##############################################################################
# Function: Verify secrets (zsh array)
##############################################################################
verify_secrets() {
    print ""
    print -P "%F{blue}Verifying secrets...%f"
    
    local required_secrets=(
        ssh_host
        ssh_port
        ssh_user
        db_host
        db_port
        db_name
        db_user
        db_pass
        smtp_host
        smtp_port
        smtp_user
        smtp_pass
        teams_webhook_url
        special_teams_email
        internal_recipients
        prominence_email_recipients
        seatraders_email_recipients
        ssh_key_content
        ssh_ubuntu_key_content
    )
    
    local missing_secrets=()
    
    for secret in $required_secrets; do
        if docker secret ls --format "{{.Name}}" | grep -q "^${secret}$"; then
            print -P "%F{green}✓ $secret%f"
        else
            print -P "%F{red}✗ $secret%f"
            missing_secrets+=($secret)
        fi
    done
    
    if [[ ${#missing_secrets[@]} -eq 0 ]]; then
        print -P "%F{green}All required secrets are present!%f"
        return 0
    else
        print -P "%F{red}Missing secrets: ${missing_secrets[*]}%f"
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
    
    print ""
    print -P "%F{green}===========================================================%f"
    print -P "%F{green}  Docker Secrets initialized successfully!%f"
    print -P "%F{green}===========================================================%f"
    print ""
    print -P "%F{blue}Next steps:%f"
    print "  1. Deploy your application:"
    print "     docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
    print ""
    print "  2. Check application logs:"
    print "     docker-compose logs -f alerts"
    print ""
    print "  3. Verify the application is running:"
    print "     docker-compose ps"
    print ""
}

# Run main function
main
