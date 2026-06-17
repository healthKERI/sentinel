#!/bin/bash
#
# Sentinel Systemd Installation Script
#
# This script installs the Sentinel systemd template unit file and sets up
# the necessary directories and permissions for running Sentinel as a service.
#
# Usage: sudo ./install.sh
#

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
   exit 1
fi

echo -e "${GREEN}=== Sentinel Systemd Installation ===${NC}\n"

# Create sentinel system user if it doesn't exist
if id "sentinel" &>/dev/null; then
    echo -e "${YELLOW}User 'sentinel' already exists${NC}"
else
    echo "Creating system user 'sentinel'..."
    useradd --system --no-create-home --shell /usr/sbin/nologin sentinel
    echo -e "${GREEN}✓ Created sentinel user${NC}"
fi

# Create required directories
echo "Creating required directories..."
mkdir -p /etc/sentinel
mkdir -p /var/lib/sentinel
mkdir -p /var/log/sentinel
mkdir -p /usr/local/sentinel

echo -e "${GREEN}✓ Created directories${NC}"

# Set ownership and permissions
echo "Setting ownership and permissions..."
chown root:sentinel /etc/sentinel
chmod 750 /etc/sentinel

chown sentinel:sentinel /var/lib/sentinel
chmod 750 /var/lib/sentinel

chown sentinel:sentinel /var/log/sentinel
chmod 750 /var/log/sentinel

chown sentinel:sentinel /usr/local/sentinel
chmod 750 /usr/local/sentinel

echo -e "${GREEN}✓ Set permissions${NC}"

# Copy systemd unit file
echo "Installing systemd unit file..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "${SCRIPT_DIR}/sentinel@.service" /etc/systemd/system/
chmod 644 /etc/systemd/system/sentinel@.service

echo -e "${GREEN}✓ Installed sentinel@.service${NC}"

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

echo -e "${GREEN}✓ Reloaded systemd${NC}"

echo -e "\n${GREEN}=== Installation Complete ===${NC}\n"

# Print usage instructions
cat <<'EOF'
Next steps:

1. Create a configuration file for your instance:
   sudo nano /etc/sentinel/myinstance.conf

   You can use the examples in examples/configs/ as templates.

2. Set proper permissions on your config file:
   sudo chown root:sentinel /etc/sentinel/myinstance.conf
   sudo chmod 640 /etc/sentinel/myinstance.conf

3. Enable the service to start on boot:
   sudo systemctl enable sentinel@myinstance

4. Start the service:
   sudo systemctl start sentinel@myinstance

5. Check the service status:
   sudo systemctl status sentinel@myinstance

6. View logs:
   sudo journalctl -u sentinel@myinstance -f

You can run multiple instances by creating additional config files
and enabling them with different instance names:
   sentinel@prod, sentinel@dev, sentinel@test, etc.

For more information, see contrib/systemd/README.md
EOF
