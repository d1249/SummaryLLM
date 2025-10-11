# Troubleshooting Guide

## Common Issues and Solutions

### 1. Configuration Errors

#### Error: "Field required [type=missing, input_value={}, input_type=dict]"

**Cause**: Missing required configuration values for EWS or LLM.

**Solution**:
```bash
# Check your .env file
cat .env

# Ensure all required variables are set:
# EWS_PASSWORD=your_password
# EWS_USER_UPN=user@corp.com
# EWS_ENDPOINT=https://ews.corp.com/EWS/Exchange.asmx
# LLM_TOKEN=your_token
# LLM_ENDPOINT=https://llm-gw.corp.com/api/v1/chat
```

#### Error: "python-dotenv could not parse statement"

**Cause**: Invalid syntax in .env file.

**Solution**:
- Remove quotes around values: `PASSWORD=value` not `PASSWORD="value"`
- No spaces around `=`: `KEY=value` not `KEY = value`
- Use `#` for comments, not `//`

### 2. EWS Connection Issues

#### Error: "SSL certificate verification failed"

**Cause**: Corporate CA certificate not found or invalid.

**Solution**:
```bash
# Check if CA certificate exists
ls -la /etc/ssl/corp-ca.pem

# Verify certificate
openssl x509 -in /etc/ssl/corp-ca.pem -text -noout

# Update config to point to correct path
# In config.yaml: verify_ca: "/path/to/your/corp-ca.pem"
```

#### Error: "NTLM authentication failed"

**Cause**: Invalid credentials or UPN format.

**Solution**:
```bash
# Verify UPN format (should include domain)
echo $EWS_USER_UPN  # Should be: user@corp.com

# Test credentials manually
python3 -c "
from exchangelib import Credentials, Account
creds = Credentials('$EWS_USER_UPN', '$EWS_PASSWORD')
print('Credentials created successfully')
"
```

### 3. LLM Gateway Issues

#### Error: "HTTP 401 Unauthorized"

**Cause**: Invalid or expired LLM token.

**Solution**:
```bash
# Check token format
echo $LLM_TOKEN | wc -c  # Should be reasonable length

# Test token manually
curl -H "Authorization: Bearer $LLM_TOKEN" "$LLM_ENDPOINT/health"
```

#### Error: "HTTP 429 Too Many Requests"

**Cause**: Rate limiting from LLM Gateway.

**Solution**:
- Wait before retrying
- Check if you have multiple instances running
- Verify rate limits in LLM Gateway configuration

### 4. Dry-Run Mode

#### Testing without LLM calls

Use dry-run mode to test EWS connectivity and normalization:

```bash
# Test dry-run mode
python3 -m digest_core.cli --dry-run

# Expected output: "Dry-run mode: ingest+normalize only"
# Should fail with configuration error (expected without real credentials)
```

### 5. Docker Issues

#### Error: "Address already in use"

**Cause**: Ports 9108 or 9109 already in use.

**Solution**:
```bash
# Check what's using the ports
lsof -i :9108
lsof -i :9109

# Kill existing processes or use different ports
docker run -p 9109:9109 -p 9108:9108 ...
```

#### Error: "Permission denied" on volume mounts

**Cause**: Incorrect file permissions.

**Solution**:
```bash
# Fix directory permissions
sudo mkdir -p /opt/digest/out /opt/digest/.state
sudo chown -R 1001:1001 /opt/digest/
sudo chmod -R 755 /opt/digest/
```

### 6. Test Issues

#### Error: "ModuleNotFoundError: No module named 'digest_core'"

**Cause**: PYTHONPATH not set correctly.

**Solution**:
```bash
# Set PYTHONPATH before running
export PYTHONPATH=/path/to/digest-core/src
python3 -m digest_core.cli --help

# Or run from project root
cd /path/to/digest-core
PYTHONPATH=src python3 -m digest_core.cli --help
```

### 7. Logging and Debugging

#### Enable debug logging

```bash
# Set log level to DEBUG
export DIGEST_LOG_LEVEL=DEBUG
python3 -m digest_core.cli --dry-run
```

#### Check Prometheus metrics

```bash
# Access metrics endpoint
curl http://localhost:9108/metrics

# Check specific metrics
curl http://localhost:9108/metrics | grep digest_
```

#### Health check endpoints

```bash
# Check health
curl http://localhost:9109/healthz

# Check readiness
curl http://localhost:9109/readyz
```

### 8. Performance Issues

#### High memory usage

**Cause**: Large email volumes or inefficient processing.

**Solution**:
- Reduce `lookback_hours` in config
- Increase `page_size` for EWS pagination
- Monitor memory usage with `htop` or `docker stats`

#### Slow processing

**Cause**: Network latency or LLM Gateway delays.

**Solution**:
- Check network connectivity to EWS and LLM Gateway
- Monitor LLM Gateway response times
- Consider increasing timeouts in config

### 9. Getting Help

#### Environment diagnostics

Run the diagnostics script:

```bash
./scripts/print_env.sh
```

This will show:
- Python version and tools
- Environment variables status
- Network connectivity
- Directory permissions
- CA certificate status

#### Collect logs

```bash
# Run with verbose logging
DIGEST_LOG_LEVEL=DEBUG python3 -m digest_core.cli --dry-run 2>&1 | tee debug.log

# Check structured logs
cat debug.log | jq .
```

#### Report issues

When reporting issues, include:
1. Output of `./scripts/print_env.sh`
2. Relevant log files
3. Configuration (without secrets)
4. Error messages
5. Steps to reproduce
