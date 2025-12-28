# IPAI MCP Finance Tools

Finance-specific MCP (Model Context Protocol) tools for InsightPulse AI, extending the base `mcp_server` module with accounting operations.

## Smart Delta Classification

**GAP_DELTA** — Extends mcp_server with finance domain logic, does not replace core functionality.

## Features

### Query Tools (Read-Only)
- **get_trial_balance**: Retrieve trial balance with hierarchy, filters, date ranges
- **get_aging_report**: AR/AP aging analysis with customizable buckets

### Create Tools (Require Approval)
- **create_journal_entry**: Safe JE creation with double-entry validation, period lock checks

### Workflow Tools
- **run_month_end_step**: Orchestrated month-end closing with checkpoints

### Compliance Tools
- **generate_bir_2307**: Philippine BIR Form 2307 generation (DAT, XLSX, PDF)

## Installation

### Prerequisites
- Odoo 18 CE
- `mcp_server` module (Ivanov's MCP Server)
- Account module with accountant features

### Install
```bash
# Copy to addons directory
cp -r ipai_mcp_finance /path/to/addons/

# Update module list and install
odoo-bin -d mydb -u base --stop-after-init
odoo-bin -d mydb -i ipai_mcp_finance --stop-after-init
```

## Configuration

1. Go to **Accounting → Configuration → MCP Finance → Configuration**
2. Enable/disable tools per company
3. Set approval thresholds for journal entries
4. Configure audit logging

## API Endpoints

### Health Check
```
GET /mcp/finance/health
```

### List Available Tools
```
GET /mcp/finance/tools
Authorization: Bearer <api_key>
```

### Execute Tool
```
POST /mcp/finance/tools/<tool_name>/execute
Authorization: Bearer <api_key>
Content-Type: application/json

{
    "params": {
        "date_from": "2025-01-01",
        "date_to": "2025-12-31"
    }
}
```

### Direct Endpoints
- `POST /mcp/finance/trial-balance`
- `POST /mcp/finance/journal-entry`
- `POST /mcp/finance/bir-2307`

## Usage Examples

### Trial Balance
```json
{
    "date_from": "2025-01-01",
    "date_to": "2025-12-31",
    "hierarchy": true,
    "include_zero": false
}
```

### Journal Entry
```json
{
    "journal_code": "MISC",
    "date": "2025-12-31",
    "ref": "Month-end accrual - Dec 2025",
    "lines": [
        {"account": "620100", "debit": 50000, "credit": 0, "name": "Rent expense"},
        {"account": "210100", "debit": 0, "credit": 50000, "name": "Accrued expenses"}
    ],
    "auto_post": false
}
```

### BIR 2307
```json
{
    "period": "2025-Q4",
    "output_format": "dat"
}
```

## Security

### Groups
- **MCP Finance User**: Read-only tools (trial balance, aging)
- **MCP Finance Manager**: All tools including journal entries
- **MCP Finance Administrator**: Configuration and full audit access

### Safety Controls
- Journal entries created in draft by default
- Period lock validation before any writes
- Double-entry balance validation
- Comprehensive audit logging
- Amount thresholds for escalated approval

## Integration with mcp-server-odoo

This module works alongside Ivanov's `mcp_server` module:

```json
{
    "mcpServers": {
        "odoo": {
            "command": "uvx",
            "args": ["mcp-server-odoo"],
            "env": {
                "ODOO_URL": "https://your-odoo.com",
                "ODOO_API_KEY": "your-key"
            }
        }
    }
}
```

The base module handles generic CRUD. This module adds:
- Finance-specific validation
- Accounting workflows
- BIR compliance
- Audit trail

## License

AGPL-3 — Open source, marketplace-ready

## Author

InsightPulse AI / TBWA Finance

## Links

- [InsightPulse Odoo Repository](https://github.com/jgtolentino/insightpulse-odoo)
- [mcp-server-odoo](https://github.com/ivnvxd/mcp-server-odoo)
- [Odoo MCP Server App](https://apps.odoo.com/apps/modules/19.0/mcp_server)
