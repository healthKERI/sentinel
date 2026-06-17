# Sentinel Configuration Files

This directory contains example configuration files for Sentinel. These examples demonstrate different deployment scenarios and configuration options.

## Configuration File Format

Sentinel uses YAML format for configuration files. When running as a systemd service, configuration files should be placed in `/etc/sentinel/` and named to match the service instance name.

For example:
- `sentinel@prod.service` → `/etc/sentinel/prod.conf`
- `sentinel@dev.service` → `/etc/sentinel/dev.conf`

## Example Configurations

### sentinel-local.conf

Local mode configuration for running Sentinel with direct witness querying:

```yaml
name: sentinel-db-local
alias: sentinel-local
bran: "YourPasscodeHere123456"

base: /var/lib/sentinel/local
export_dir: /usr/local/sentinel/local
logfile: /var/log/sentinel/local.log
loglevel: INFO

local: true
uxd: false
```

**Use case**: Development, testing, or standalone deployments where Sentinel queries witnesses directly.

### sentinel-healthkeri.conf

HealthKERI network configuration for production healthcare monitoring:

```yaml
name: sentinel-db-healthkeri
alias: sentinel-healthkeri
bran: "AnotherPasscode7890123"

base: /var/lib/sentinel/healthkeri
export_dir: /usr/local/sentinel/healthkeri
logfile: /var/log/sentinel/healthkeri.log
loglevel: INFO

local: false
uxd: true

registrar:
  url: https://registrar.healthkeri.com/api
  aid: EXq5YqaL6L48pf0fu7IUhL0JRaU2_RxFP0AL43wYn148
  oobi: http://registrar.healthkeri.com/oobi/EXq5YqaL6L48pf0fu7IUhL0JRaU2_RxFP0AL43wYn148
```

**Use case**: Production deployments integrated with the HealthKERI Watcher Network.

## Configuration Parameters

### Required Parameters

#### `name`
- **Type**: String
- **Description**: Database name for the Sentinel keystore
- **Example**: `sentinel-db-prod`
- **Notes**: Should be unique per instance

#### `alias`
- **Type**: String
- **Description**: Human-readable alias for the Sentinel instance
- **Example**: `sentinel-prod`
- **Notes**: Used in logging and identification

### Optional Core Parameters

#### `bran`
- **Type**: String (22 characters)
- **Description**: Passcode/seed for keystore encryption
- **Example**: `"1234567890123456789012"`
- **Security**:
  - Must be exactly 22 characters
  - Keep this value secret
  - Use unique values per instance
  - Consider using systemd credentials for production
- **Default**: Generated randomly if not provided

#### `base`
- **Type**: Path
- **Description**: Base directory for keystore data
- **Example**: `/var/lib/sentinel/prod`
- **Default**: `~/.sentinel/` (not recommended for systemd)
- **Notes**: Sentinel user must have write access

#### `export_dir`
- **Type**: Path
- **Description**: Directory for exported credential data
- **Example**: `/usr/local/sentinel/prod`
- **Default**: `{base}/exports`
- **Notes**: Sentinel user must have write access

#### `logfile`
- **Type**: Path
- **Description**: Path to log file
- **Example**: `/var/log/sentinel/prod.log`
- **Default**: None (stdout only)
- **Notes**:
  - Logs also go to systemd journal
  - Directory must be writable by sentinel user
  - Consider log rotation for production

#### `loglevel`
- **Type**: String
- **Description**: Logging verbosity level
- **Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Default**: `INFO`
- **Notes**: Use `DEBUG` for troubleshooting, `INFO` for production

### Network Mode Parameters

#### `local`
- **Type**: Boolean
- **Description**: Enable local witness querying mode
- **Default**: `false`
- **Notes**:
  - `true`: Query witnesses directly (standalone mode)
  - `false`: Use watcher network (requires registrar/issuer config)

#### `uxd`
- **Type**: Boolean
- **Description**: Enable Unix Domain Socket mode
- **Default**: `false`
- **Notes**:
  - `true`: Use Unix domain sockets (recommended for same-host communication)
  - `false`: Use TCP sockets (required for remote communication)

### Registrar Configuration

Used when `local: false` to connect to a watcher network:

#### `registrar.url`
- **Type**: URL
- **Description**: Registrar API endpoint
- **Example**: `https://registrar.healthkeri.com/api`

#### `registrar.aid`
- **Type**: String (KERI AID)
- **Description**: Registrar's Autonomic Identifier
- **Example**: `EXq5YqaL6L48pf0fu7IUhL0JRaU2_RxFP0AL43wYn148`

#### `registrar.oobi`
- **Type**: URL
- **Description**: Out-Of-Band Introduction URL for registrar
- **Example**: `http://registrar.healthkeri.com/oobi/EXq5YqaL6L48pf0fu7IUhL0JRaU2_RxFP0AL43wYn148`

### Issuer Configuration

Optional configuration for connecting to specific issuers:

#### `issuer.url`
- **Type**: URL
- **Description**: Issuer API endpoint
- **Example**: `https://issuer.example.com/api`

#### `issuer.aid`
- **Type**: String (KERI AID)
- **Description**: Issuer's Autonomic Identifier

#### `issuer.oobi`
- **Type**: URL
- **Description**: Out-Of-Band Introduction URL for issuer

## Instance Naming Conventions

### Configuration File Names

Use lowercase with hyphens for multi-word instance names:

**Good**:
- `prod.conf`
- `dev-test.conf`
- `health-keri.conf`
- `staging-env.conf`

**Avoid**:
- `PROD.conf` (uppercase)
- `dev_test.conf` (underscores)
- `devTest.conf` (camelCase)
- `dev test.conf` (spaces)

### Instance-Specific Directories

Each instance should use distinct directories to avoid conflicts:

```yaml
# prod.conf
base: /var/lib/sentinel/prod
export_dir: /usr/local/sentinel/prod
logfile: /var/log/sentinel/prod.log

# dev.conf
base: /var/lib/sentinel/dev
export_dir: /usr/local/sentinel/dev
logfile: /var/log/sentinel/dev.log
```

## Security Best Practices

### File Permissions

Configuration files contain sensitive data and should be protected:

```bash
# Set ownership and permissions
sudo chown root:sentinel /etc/sentinel/instance.conf
sudo chmod 640 /etc/sentinel/instance.conf
```

This allows:
- Root to read and write (for management)
- Sentinel group to read (required for service)
- No access for other users

### Passcode Management

The `bran` parameter is sensitive and should be:

1. **Unique per instance**: Never reuse passcodes
2. **Randomly generated**: Use cryptographically secure random values
3. **Properly stored**: Consider using systemd credentials or secrets management
4. **Never committed**: Add `*.conf` to `.gitignore` for local configs

Example of generating a secure passcode:

```bash
# Generate 22-character random passcode
openssl rand -base64 22 | cut -c1-22
```

### Network Security

When using `local: false`:
- Use HTTPS URLs for registrar/issuer endpoints
- Verify TLS certificates
- Use firewall rules to restrict network access
- Consider using VPN or private networks

## Configuration Examples by Use Case

### Development Environment

```yaml
name: sentinel-db-dev
alias: sentinel-dev
bran: "DevPasscode1234567890"

base: /var/lib/sentinel/dev
export_dir: /usr/local/sentinel/dev
logfile: /var/log/sentinel/dev.log
loglevel: DEBUG  # Verbose logging for development

local: true  # Standalone mode
uxd: false   # TCP for testing
```

### Production Environment

```yaml
name: sentinel-db-prod
alias: sentinel-prod
bran: "ProdPasscode123456789"  # Use secure random value

base: /var/lib/sentinel/prod
export_dir: /usr/local/sentinel/prod
logfile: /var/log/sentinel/prod.log
loglevel: INFO  # Standard production logging

local: false  # Watcher network mode
uxd: true     # Unix sockets for performance

registrar:
  url: https://registrar.healthkeri.com/api
  aid: EXq5YqaL6L48pf0fu7IUhL0JRaU2_RxFP0AL43wYn148
  oobi: http://registrar.healthkeri.com/oobi/EXq5YqaL6L48pf0fu7IUhL0JRaU2_RxFP0AL43wYn148
```

### Testing Environment

```yaml
name: sentinel-db-test
alias: sentinel-test
bran: "TestPasscode1234567890"

base: /var/lib/sentinel/test
export_dir: /usr/local/sentinel/test
logfile: /var/log/sentinel/test.log
loglevel: DEBUG

local: true  # Isolated testing
uxd: false
```

## Validation

### Check Configuration Syntax

Sentinel will validate the configuration on startup. To test without starting the service:

```bash
# Test configuration (if supported)
sentinel start --config /etc/sentinel/prod.conf --validate
```

### Common Configuration Errors

1. **Invalid YAML syntax**
   - Use spaces, not tabs, for indentation
   - Quote string values containing special characters
   - Ensure proper nesting for registrar/issuer sections

2. **Missing required parameters**
   - Both `name` and `alias` are required
   - When `local: false`, registrar configuration is required

3. **Path permissions**
   - Ensure `base`, `export_dir`, and `logfile` directories exist
   - Verify sentinel user has write access

4. **Invalid passcode length**
   - `bran` must be exactly 22 characters if provided

## Migrating Configurations

### From Development to Production

When moving from development to production:

1. Change instance name and alias
2. Update directory paths to production locations
3. Generate new unique `bran` passcode
4. Set `loglevel` to `INFO`
5. Update registrar/issuer endpoints to production URLs
6. Review and apply security best practices

### From Standalone to Network Mode

To switch from local to network mode:

1. Set `local: false`
2. Add registrar configuration block
3. Consider enabling `uxd: true` for performance
4. Test connectivity to registrar before deploying

## Troubleshooting

### Configuration not loading

```bash
# Check file exists and has correct name
ls -la /etc/sentinel/

# Verify file permissions
ls -la /etc/sentinel/instance.conf

# Check systemd logs for configuration errors
sudo journalctl -u sentinel@instance -n 50
```

### Directory permission errors

```bash
# Verify sentinel user can access directories
sudo -u sentinel ls /var/lib/sentinel/instance
sudo -u sentinel touch /var/log/sentinel/instance.log

# Fix ownership if needed
sudo chown -R sentinel:sentinel /var/lib/sentinel
sudo chown -R sentinel:sentinel /var/log/sentinel
```

### Connection errors (network mode)

```bash
# Test registrar connectivity
curl https://registrar.healthkeri.com/api

# Verify OOBI endpoint
curl http://registrar.healthkeri.com/oobi/EXq5YqaL6L48pf0fu7IUhL0JRaU2_RxFP0AL43wYn148

# Check network mode settings
grep -E "local|uxd|registrar" /etc/sentinel/instance.conf
```

## Further Reading

- [Systemd Integration](../../contrib/systemd/README.md)
- [Sentinel Documentation](../../docs/)
- [KERI Specification](https://github.com/WebOfTrust/keri)
