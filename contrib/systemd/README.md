# Sentinel Systemd Integration

This directory contains a systemd template unit file for running Sentinel as a system service on Linux systems. The template allows running multiple independent Sentinel instances simultaneously, each with its own configuration.

## Overview

The `sentinel@.service` template follows the same pattern as `wg-quick@` and other systemd templates:
- `sentinel@prod.service` → uses `/etc/sentinel/prod.conf`
- `sentinel@dev.service` → uses `/etc/sentinel/dev.conf`
- `sentinel@test.service` → uses `/etc/sentinel/test.conf`

Each instance runs independently with its own:
- Configuration file
- Data directory
- Log file
- Process

## Installation

### Automated Installation

The easiest way to install is using the provided script:

```bash
cd contrib/systemd
sudo ./install.sh
```

This script will:
1. Create a dedicated `sentinel` system user
2. Create required directories (`/etc/sentinel`, `/var/lib/sentinel`, `/var/log/sentinel`, `/usr/local/sentinel`)
3. Set proper ownership and permissions
4. Install the systemd unit file
5. Reload the systemd daemon

### Manual Installation

If you prefer to install manually:

```bash
# Create sentinel system user
sudo useradd --system --no-create-home --shell /usr/sbin/nologin sentinel

# Create required directories
sudo mkdir -p /etc/sentinel
sudo mkdir -p /var/lib/sentinel
sudo mkdir -p /var/log/sentinel
sudo mkdir -p /usr/local/sentinel

# Set ownership and permissions
sudo chown root:sentinel /etc/sentinel
sudo chmod 750 /etc/sentinel

sudo chown sentinel:sentinel /var/lib/sentinel
sudo chmod 750 /var/lib/sentinel

sudo chown sentinel:sentinel /var/log/sentinel
sudo chmod 750 /var/log/sentinel

sudo chown sentinel:sentinel /usr/local/sentinel
sudo chmod 750 /usr/local/sentinel

# Copy unit file
sudo cp sentinel@.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/sentinel@.service

# Reload systemd
sudo systemctl daemon-reload
```

## Usage

### 1. Create Configuration File

Create a configuration file in `/etc/sentinel/` for your instance. See `examples/configs/` for templates.

```bash
sudo nano /etc/sentinel/prod.conf
```

Example minimal configuration:

```yaml
name: sentinel-db-prod
alias: sentinel-prod
bran: "YourSecurePasscode123"  # 22 characters

base: /var/lib/sentinel/prod
export_dir: /usr/local/sentinel/prod
logfile: /var/log/sentinel/prod.log
loglevel: INFO

local: true
uxd: false
```

Set proper permissions:

```bash
sudo chown root:sentinel /etc/sentinel/prod.conf
sudo chmod 640 /etc/sentinel/prod.conf
```

### 2. Enable and Start Service

```bash
# Enable service to start on boot
sudo systemctl enable sentinel@prod

# Start the service
sudo systemctl start sentinel@prod

# Check status
sudo systemctl status sentinel@prod
```

### 3. Managing the Service

```bash
# Stop the service
sudo systemctl stop sentinel@prod

# Restart the service
sudo systemctl restart sentinel@prod

# Disable service (prevent auto-start on boot)
sudo systemctl disable sentinel@prod

# View logs
sudo journalctl -u sentinel@prod -f

# View logs from the last hour
sudo journalctl -u sentinel@prod --since "1 hour ago"

# View only errors
sudo journalctl -u sentinel@prod -p err
```

## Running Multiple Instances

You can run multiple Sentinel instances simultaneously by creating multiple configuration files:

```bash
# Create configurations
sudo cp /etc/sentinel/prod.conf /etc/sentinel/dev.conf
sudo cp /etc/sentinel/prod.conf /etc/sentinel/test.conf

# Edit each config with instance-specific settings
sudo nano /etc/sentinel/dev.conf
sudo nano /etc/sentinel/test.conf

# Enable and start all instances
sudo systemctl enable sentinel@prod sentinel@dev sentinel@test
sudo systemctl start sentinel@prod sentinel@dev sentinel@test

# Check all instances
sudo systemctl status 'sentinel@*'
```

Each instance will have its own:
- Configuration: `/etc/sentinel/{instance}.conf`
- Data directory: `/var/lib/sentinel/{instance}/`
- Export directory: `/usr/local/sentinel/{instance}/`
- Log file: `/var/log/sentinel/{instance}.log`
- Journal identifier: `sentinel-{instance}`

## Security Features

The unit file includes comprehensive security hardening:

### User Context
- Runs as unprivileged `sentinel` user (not root)
- No elevated capabilities required

### Filesystem Protection
- `ProtectSystem=strict`: Read-only root filesystem
- `ProtectHome=true`: No access to user home directories
- `PrivateTmp=true`: Private `/tmp` directory
- Write access only to required directories:
  - `/var/lib/sentinel/{instance}/` (keystore data)
  - `/var/log/sentinel/` (logs)
  - `/usr/local/sentinel/` (exports)

### Kernel Protection
- `ProtectKernelTunables=true`: Kernel parameters read-only
- `ProtectKernelModules=true`: Cannot load kernel modules
- `ProtectControlGroups=true`: Control groups read-only
- `LockPersonality=true`: Prevent personality changes

### System Call Filtering
- Allows only standard service system calls
- Blocks privileged operations
- Prevents privilege escalation

### Other Restrictions
- `NoNewPrivileges=true`: Cannot gain new privileges
- `RestrictRealtime=true`: No realtime scheduling
- `RestrictNamespaces=true`: Cannot create namespaces
- `RestrictSUIDSGID=true`: Cannot use SUID/SGID
- `CapabilityBoundingSet=`: No capabilities

### Service Behavior
- Automatic restart on failure with exponential backoff
- Graceful shutdown via SIGTERM with 30-second timeout
- Starts after network is online
- Logs to systemd journal

## Verification

### Validate Unit File

Check the unit file for syntax errors:

```bash
systemd-analyze verify /etc/systemd/system/sentinel@.service
```

### Security Analysis

Check the security posture (target score < 3.0):

```bash
sudo systemd-analyze security sentinel@prod
```

### Test Graceful Shutdown

Verify SIGTERM handling:

```bash
# Start service
sudo systemctl start sentinel@test

# Stop and check logs for graceful shutdown
sudo systemctl stop sentinel@test
sudo journalctl -u sentinel@test -n 50
```

Look for shutdown messages indicating graceful termination.

### Test Automatic Restart

Verify restart-on-failure:

```bash
# Get PID
sudo systemctl status sentinel@test

# Kill process
sudo kill -9 <PID>

# Check that it restarted
sudo systemctl status sentinel@test
sudo journalctl -u sentinel@test -n 20
```

## Troubleshooting

### Service fails to start

```bash
# Check detailed status
sudo systemctl status sentinel@instance -l

# Check recent logs
sudo journalctl -u sentinel@instance -n 50

# Check for errors
sudo journalctl -u sentinel@instance -p err
```

Common issues:
- **Permission denied**: Check file ownership and permissions on config file and directories
- **Config file not found**: Ensure `/etc/sentinel/{instance}.conf` exists
- **Sentinel binary not found**: Check that `sentinel` is installed at `/usr/local/bin/sentinel`

### Cannot write to directories

```bash
# Verify directory ownership
ls -la /var/lib/sentinel/
ls -la /var/log/sentinel/
ls -la /usr/local/sentinel/

# Should be owned by sentinel:sentinel
# Fix if needed:
sudo chown -R sentinel:sentinel /var/lib/sentinel
sudo chown -R sentinel:sentinel /var/log/sentinel
sudo chown -R sentinel:sentinel /usr/local/sentinel
```

### Service keeps restarting

```bash
# Check for crash logs
sudo journalctl -u sentinel@instance -f

# Check exit codes
sudo systemctl status sentinel@instance
```

The service will restart automatically on failure (up to 5 times in 5 minutes). Check logs to identify the root cause.

### View configuration being used

```bash
# Show the effective configuration
sudo systemctl cat sentinel@instance

# Show environment variables
sudo systemctl show sentinel@instance --property=Environment
```

## Configuration File Security

### File Permissions

Configuration files contain sensitive data (passcodes) and should be protected:

```bash
# Recommended permissions
sudo chown root:sentinel /etc/sentinel/instance.conf
sudo chmod 640 /etc/sentinel/instance.conf
```

This allows:
- Root to read and write
- Sentinel group to read (required for service)
- No access for others

### Secret Management

For enhanced security, consider using systemd credentials for sensitive values:

```ini
# Future enhancement - not yet implemented
[Service]
LoadCredential=bran:/etc/sentinel/secrets/prod.bran
```

## Logging

### Systemd Journal

Logs are sent to the systemd journal with identifier `sentinel-{instance}`:

```bash
# Follow logs in real-time
sudo journalctl -u sentinel@instance -f

# Logs since boot
sudo journalctl -u sentinel@instance -b

# Logs from specific time
sudo journalctl -u sentinel@instance --since "2024-01-01 10:00"

# Export to file
sudo journalctl -u sentinel@instance > sentinel-instance.log
```

### File Logs

If configured with `logfile` parameter, logs are also written to the specified file:

```bash
# View log file
sudo tail -f /var/log/sentinel/instance.log

# Rotate logs (if using logrotate)
sudo logrotate /etc/logrotate.d/sentinel
```

## Performance Tuning

### Startup Timeout

The Sentinel startup process can take up to 5 minutes for large keystores. If you experience timeout issues:

```ini
[Service]
TimeoutStartSec=300
```

### Resource Limits

Add resource limits if needed:

```ini
[Service]
MemoryMax=2G
CPUQuota=80%
```

## Integration with systemd Features

### Service Dependencies

Make Sentinel depend on other services:

```ini
[Unit]
After=network-online.target postgresql.service
Requires=postgresql.service
```

### Email Notifications on Failure

Configure email alerts (requires mail system):

```ini
[Service]
OnFailure=status-email@%i.service
```

## Uninstallation

To remove Sentinel systemd integration:

```bash
# Stop and disable all instances
sudo systemctl stop 'sentinel@*'
sudo systemctl disable 'sentinel@*'

# Remove unit file
sudo rm /etc/systemd/system/sentinel@.service
sudo systemctl daemon-reload

# Optionally remove user and directories
sudo userdel sentinel
sudo rm -rf /etc/sentinel
sudo rm -rf /var/lib/sentinel
sudo rm -rf /var/log/sentinel
sudo rm -rf /usr/local/sentinel
```

## Further Reading

- [systemd.service](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [systemd.unit](https://www.freedesktop.org/software/systemd/man/systemd.unit.html)
- [systemd.exec](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)
- [Sentinel Configuration](../../examples/configs/README.md)
