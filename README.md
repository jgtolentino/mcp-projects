# mcp-projects

InsightPulse AI Finance SSC automation with Odoo MCP integration

## Overview

This repository contains the **ipai_mcp_finance** Odoo module and related infrastructure for extending Odoo CE 18.0 with Claude-compatible MCP (Model Context Protocol) tools for finance operations.

## Architecture

```
Claude Desktop/API
   ↓ MCP Protocol
mcp-server-odoo (base)
   ↓ Smart Delta Extension
ipai_mcp_finance (this module)
   ↓ XML-RPC/REST
Odoo CE 18.0 (OCA)
   ↓
Supabase PostgreSQL
```

## Key Features

### Finance MCP Tools

1. **get_trial_balance** - Query trial balance with account hierarchy
   - Multi-company support
   - Date range filtering
   - Hierarchical account structure

2. **create_journal_entry** - Safe journal entry creation
   - Double-entry validation (debits = credits)
   - Period lock checking
   - Draft by default (requires approval)
   - Amount threshold controls

3. **generate_bir_2307** - BIR 2307 form generation
   - DAT file format (BIR-ready)
   - XLSX export option
   - Multi-vendor support
   - Quarterly aggregation

### Safety Controls

- ✅ Period lock validation
- ✅ Double-entry validation (0.01 tolerance)
- ✅ Draft-by-default with approval workflow
- ✅ Configurable amount thresholds
- ✅ Complete audit trail

## Quick Start

### Prerequisites

- Odoo CE 18.0 instance
- `mcp_server` module installed (Ivanov's base MCP module)
- PostgreSQL 15+ (Supabase)
- Claude Desktop or API access

### Installation

```bash
# 1. Clone repository
git clone https://github.com/jgtolentino/mcp-projects.git
cd mcp-projects

# 2. Deploy to Odoo (development)
docker cp addons/ipai_mcp_finance odoo:/mnt/extra-addons/
docker exec odoo odoo -d mydb -u base -i ipai_mcp_finance --stop-after-init

# 3. Configure MCP in Claude Desktop
# Add to ~/.claude/mcp_config.json:
{
  "odoo-finance": {
    "command": "odoo-mcp-client",
    "args": ["--url", "https://odoo.insightpulseai.net", "--database", "production"],
    "env": {
      "ODOO_API_KEY": "your-api-key"
    }
  }
}

# 4. Restart Claude Desktop
```

### Usage Examples

**Query Trial Balance**:
```
User: "Show me the trial balance for December 2025"
Claude: [Uses get_trial_balance MCP tool]
```

**Create Journal Entry**:
```
User: "Create an accrual JE for vendor invoice 50000"
Claude: [Uses create_journal_entry with validation]
```

**Generate BIR Form**:
```
User: "Generate 2307 for Q4 2025 vendors"
Claude: [Uses generate_bir_2307 tool]
```

## Repository Structure

```
mcp-projects/
├── CLAUDE.md                        # Project orchestration rules
├── README.md                        # This file
├── addons/                          # Odoo modules
│   └── ipai_mcp_finance/           # Finance MCP tools
│       ├── __manifest__.py
│       ├── models/                  # Config & audit models
│       ├── tools/                   # MCP tool implementations
│       ├── controllers/             # HTTP endpoints
│       ├── security/                # Groups & ACLs
│       ├── views/                   # Config UI
│       └── data/                    # Tool registrations
├── packages/db/sql/                # Supabase migrations
├── workflows/                       # n8n workflow definitions
├── infra/do/                       # DigitalOcean specs
├── scripts/                        # Automation scripts
├── docs/                           # Documentation
└── .github/workflows/              # CI/CD pipelines
```

## Development

### Adding a New MCP Tool

1. **Define tool implementation** in `addons/ipai_mcp_finance/tools/my_tool.py`
2. **Register in `__init__.py`** under `tools/`
3. **Add tool metadata** in `data/mcp_finance_tools.xml`
4. **Add security rules** in `security/ir.model.access.csv`
5. **Test locally** with Odoo test suite
6. **Deploy** following acceptance gates

### Running Tests

```bash
# Unit tests
odoo -d test_db -i ipai_mcp_finance --test-enable --stop-after-init

# MCP integration tests
python scripts/test_mcp_tools.py --url https://odoo.insightpulseai.net
```

## Deployment

### DigitalOcean App Platform

```bash
# Update app spec
doctl apps update <APP_ID> --spec infra/do/odoo-erp.yaml

# Force rebuild
doctl apps create-deployment <APP_ID> --force-rebuild

# Monitor logs
doctl apps logs <APP_ID> --follow
```

### Supabase Migrations

```bash
# Apply schema changes
psql "$POSTGRES_URL" -f packages/db/sql/00_mcp_audit_log.sql

# Or use Supabase CLI
supabase db push
```

## Acceptance Gates

Before marking work as complete, all gates must pass:

1. ✅ Odoo module installs without errors
2. ✅ All MCP tools registered and callable
3. ✅ Trial balance returns correct hierarchy
4. ✅ Journal entry validation blocks invalid entries
5. ✅ BIR 2307 generation produces valid DAT files
6. ✅ Audit log captures all tool executions
7. ✅ Security groups properly restrict access

## Stack

- **Odoo CE 18.0** (OCA-compliant)
- **Supabase PostgreSQL** (project_ref: xkxyvboeubffxxbebsll)
- **DigitalOcean App Platform** (fin-workspace: 29cde7a1-8280-46ad-9fdf-dea7b21a7825)
- **n8n** (workflow automation)
- **Claude Desktop/API** (MCP client)

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-tool`)
3. Commit changes (`git commit -m 'Add amazing MCP tool'`)
4. Push to branch (`git push origin feature/amazing-tool`)
5. Open Pull Request

**PR Requirements**:
- OCA compliance (AGPL-3 license, proper `__manifest__.py`)
- Tests with ≥80% coverage
- Documentation updates
- Acceptance gates passing

## License

AGPL-3.0 (OCA-compliant)

## Support

- **Issues**: https://github.com/jgtolentino/mcp-projects/issues
- **Email**: jake.tolentino@insightpulseai.net
- **Mattermost**: https://mattermost.insightpulseai.net

## Related Projects

- [mcp-server-odoo](https://apps.odoo.com/apps/modules/19.0/mcp_server) - Base MCP server for Odoo
- [Anthropic MCP Spec](https://modelcontextprotocol.io/) - Model Context Protocol specification
- [OCA Guidelines](https://odoo-community.org/) - Odoo Community Association standards
