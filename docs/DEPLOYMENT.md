# Deployment Guide - ipai_mcp_finance

Complete deployment instructions for the ipai_mcp_finance Odoo module.

## Prerequisites

1. **DigitalOcean Account**
   - Project: `fin-workspace` (29cde7a1-8280-46ad-9fdf-dea7b21a7825)
   - doctl CLI installed and authenticated

2. **Supabase Instance**
   - Project ref: `xkxyvboeubffxxbebsll`
   - PostgreSQL 15+ connection details

3. **GitHub Repository**
   - Repository: `jgtolentino/mcp-projects`
   - Secrets configured for CI/CD

4. **Claude Desktop** (for MCP client)
   - Version 1.0+ with MCP support

---

## Deployment Options

### Option 1: DigitalOcean App Platform (Recommended)

**Step 1: Configure Secrets**

```bash
# Set required secrets in GitHub
gh secret set DO_ACCESS_TOKEN --body "$DO_ACCESS_TOKEN"
gh secret set ODOO_APP_ID --body "$ODOO_APP_ID"
gh secret set SUPABASE_DB_USER --body "postgres.xkxyvboeubffxxbebsll"
gh secret set SUPABASE_DB_PASSWORD --body "$SUPABASE_PASSWORD"
gh secret set ODOO_MCP_API_KEY --body "$(openssl rand -hex 32)"
gh secret set MATTERMOST_WEBHOOK_URL --body "$MATTERMOST_WEBHOOK"
```

**Step 2: Create DigitalOcean App**

```bash
# Create new app from spec
doctl apps create --spec infra/do/odoo-mcp-finance.yaml

# Or update existing app
doctl apps update $ODOO_APP_ID --spec infra/do/odoo-mcp-finance.yaml
```

**Step 3: Trigger Deployment**

```bash
# Push to main branch triggers auto-deployment via GitHub Actions
git push origin main

# Or manually trigger deployment
doctl apps create-deployment $ODOO_APP_ID --force-rebuild --wait
```

**Step 4: Verify Deployment**

```bash
# Check app status
doctl apps get $ODOO_APP_ID

# Test health endpoint
curl -f https://odoo.insightpulseai.net/web/health

# Check MCP tool registration
python scripts/test_mcp_registration.py \
  --url https://odoo.insightpulseai.net \
  --db production
```

---

### Option 2: Docker Compose (Local Development)

**Step 1: Create docker-compose.yml**

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: odoo
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
    volumes:
      - postgres-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  odoo:
    build:
      context: .
      dockerfile: infra/docker/Dockerfile.odoo
    depends_on:
      - postgres
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_USER: odoo
      DB_PASSWORD: odoo
      DB_NAME: odoo
      WORKERS: 2
      MAX_CRON_THREADS: 1
      LIMIT_MEMORY_HARD: 2684354560
      LIMIT_MEMORY_SOFT: 2147483648
      ADDONS_PATH: /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
    volumes:
      - odoo-data:/var/lib/odoo
      - ./addons:/mnt/extra-addons
    ports:
      - "8069:8069"

volumes:
  postgres-data:
  odoo-data:
```

**Step 2: Build and Run**

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Initialize database and install module
docker-compose exec odoo odoo -d odoo -i ipai_mcp_finance --stop-after-init

# Start Odoo
docker-compose restart odoo

# View logs
docker-compose logs -f odoo
```

**Step 3: Access Odoo**

- URL: http://localhost:8069
- Database: odoo
- User: admin
- Password: admin (change immediately)

---

### Option 3: Existing Odoo Instance (Manual)

**Step 1: Copy Module**

```bash
# SSH to Odoo server
ssh odoo-erp-prod

# Copy module to addons path
sudo cp -r /path/to/ipai_mcp_finance /mnt/extra-addons/
sudo chown -R odoo:odoo /mnt/extra-addons/ipai_mcp_finance
```

**Step 2: Install Dependencies**

```bash
# Install Python dependencies
sudo pip3 install anthropic-mcp openpyxl python-dateutil
```

**Step 3: Install Module**

```bash
# Update modules list
sudo -u odoo odoo -d production -u base --stop-after-init

# Install ipai_mcp_finance
sudo -u odoo odoo -d production -i ipai_mcp_finance --stop-after-init

# Restart Odoo
sudo systemctl restart odoo
```

---

## Claude Desktop Integration

**Step 1: Configure MCP Client**

Edit `~/.claude/mcp_config.json`:

```json
{
  "odoo-finance": {
    "command": "python3",
    "args": ["-m", "odoo_mcp_client"],
    "env": {
      "ODOO_URL": "https://odoo.insightpulseai.net",
      "ODOO_DATABASE": "production",
      "ODOO_API_KEY": "your-mcp-api-key-from-odoo-config"
    }
  }
}
```

**Step 2: Install MCP Client (if needed)**

```bash
pip install odoo-mcp-client
```

**Step 3: Restart Claude Desktop**

**Step 4: Test Integration**

In Claude Desktop:
```
User: "Show me the trial balance for December 2025"
Claude: [Should use get_trial_balance MCP tool and return results]
```

---

## Acceptance Gates Verification

Run the complete acceptance test suite:

```bash
# Gate 1: Module Installation
python scripts/validate_manifest.py addons/ipai_mcp_finance/__manifest__.py

# Gate 2: MCP Tools Registration
python scripts/test_mcp_registration.py

# Gates 3-5: Tool Functionality
pytest tests/test_trial_balance.py -v
pytest tests/test_journal_entry.py -v
pytest tests/test_bir_2307.py -v

# Gate 6: Audit Log
python scripts/test_audit_log.py

# Gate 7: Security Groups
python scripts/test_security_groups.py
```

All gates must pass (exit code 0) before deployment is considered successful.

---

## Monitoring and Maintenance

### Health Checks

```bash
# App Platform health
doctl apps get $ODOO_APP_ID --format Status

# Odoo health endpoint
curl https://odoo.insightpulseai.net/web/health

# Database connectivity
psql "$POSTGRES_URL" -c "SELECT version();"
```

### Logs

```bash
# DigitalOcean app logs
doctl apps logs $ODOO_APP_ID --follow

# Local Docker logs
docker-compose logs -f odoo
```

### Scaling

```bash
# Update instance size
doctl apps update $ODOO_APP_ID --spec infra/do/odoo-mcp-finance.yaml

# Scale workers (edit odoo.conf)
WORKERS=6  # For 3 vCPU
```

---

## Rollback Procedure

If deployment fails or causes issues:

```bash
# Get last successful deployment
LAST_GOOD=$(doctl apps list-deployments $ODOO_APP_ID \
  --format ID,Phase \
  | grep ACTIVE | head -n2 | tail -n1 | awk '{print $1}')

# Rollback to last good deployment
doctl apps create-deployment $ODOO_APP_ID --deployment-id $LAST_GOOD

# Verify rollback
curl -f https://odoo.insightpulseai.net/web/health
```

Or let CI/CD handle it automatically via the `rollback-on-failure` job.

---

## Troubleshooting

### Module Not Found

```bash
# Check addons path
docker exec odoo cat /etc/odoo/odoo.conf | grep addons_path

# Verify module exists
docker exec odoo ls -la /mnt/extra-addons/ipai_mcp_finance
```

### Database Connection Errors

```bash
# Test Supabase connection
psql "$POSTGRES_URL" -c "SELECT 1;"

# Check pooler port (use 6543 not 5432)
echo $POSTGRES_URL | grep 6543
```

### MCP Tools Not Registered

```bash
# Check tool definitions
python scripts/test_mcp_registration.py --debug

# Verify data files loaded
psql "$POSTGRES_URL" -c "SELECT * FROM mcp_finance_tool;"
```

### Performance Issues

```bash
# Check worker count
docker exec odoo ps aux | grep odoo | grep -v grep

# Monitor resource usage
doctl apps tier instance-size list

# Review slow queries
psql "$POSTGRES_URL" -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

---

## Next Steps

1. **Add Remaining Tools**
   - `get_aging_report` - AP/AR aging analysis
   - `run_month_end_step` - Month-end closing workflow

2. **Integrate with n8n**
   - Create workflows for BIR deadline alerts
   - Task escalation automation
   - Monthly compliance reports

3. **Enhance Security**
   - Enable 2FA for Odoo admin accounts
   - Implement IP whitelisting
   - Add rate limiting for MCP endpoints

4. **Performance Optimization**
   - Add Redis for session storage
   - Implement query caching
   - Enable CDN for static assets

5. **Documentation**
   - Add user guides for each MCP tool
   - Create video tutorials
   - Document common workflows

---

## Support

- **Issues**: https://github.com/jgtolentino/mcp-projects/issues
- **Mattermost**: https://mattermost.insightpulseai.net
- **Email**: jake.tolentino@insightpulseai.net
