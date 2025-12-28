# CLAUDE.md — Project Orchestration Rules

## 0. Purpose

This file describes **how Claude Code should behave in THIS repo only**:
- What to execute
- What tools/CLIs are allowed
- What infra is in scope
- What gates must pass before work is considered "done"

All framework-level behavior (personas, wave mode, skills, etc.) lives in `~/.claude/CLAUDE.md` and related global docs.

---

## 1. Execution Model

- **Claude Code = orchestrator + executor** in this repo.
- Use **direct terminal access** (git, doctl, supabase, vercel, curl, odoo).
- **No guides instead of actions** – respond with runnable commands, not UI click-paths.
- Assume **execution intent by default**: once a plan is formed, act until acceptance gates pass.

---

## 2. Project Context

**Project Name**: mcp-projects
**Purpose**: InsightPulse AI Finance SSC automation with Odoo MCP integration
**Primary Stack**: Odoo CE 18.0 + n8n + Supabase + DigitalOcean

**Key Components**:
- `addons/ipai_mcp_finance/` - Finance-specific MCP tools for Odoo
- `packages/db/sql/` - Supabase migrations and schemas
- `workflows/` - n8n workflow definitions
- `infra/do/` - DigitalOcean App Platform specs
- `scripts/` - Deployment and testing automation

---

## 3. Environment Constraints

**Cloud stack (allowed)**:
- **DigitalOcean App Platform** – microservices
- **Supabase PostgreSQL** – primary DB (project_ref: xkxyvboeubffxxbebsll)
- **Supabase Storage/Vault** – files + secrets
- **Vercel** – frontend deployment (if applicable)

**DigitalOcean Infrastructure** (`fin-workspace` project: 29cde7a1-8280-46ad-9fdf-dea7b21a7825):

**Key Droplets**:
- **odoo-erp-prod**: SGP1 / 4GB RAM / 80GB Disk / 159.223.75.148
- **ocr-service-droplet**: SGP1 / 8GB RAM / 80GB Disk / 188.166.237.231

**Prohibited**:
- Azure services
- Cloudflare for this project
- Local Docker for prod deployment (debug-only)

**Allowed CLIs**:
- `doctl` – DO App Platform
- `supabase` – migrations/local dev
- `psql` – direct DB access via Supabase pooler (port 6543)
- `gh` – GitHub ops
- `curl` – HTTP checks
- `odoo` – Odoo CE tasks

---

## 4. ipai_mcp_finance Module

**Purpose**: Finance-specific MCP tools extending mcp-server-odoo base module

**Architecture**: Smart Delta pattern - extends upstream mcp-server-odoo without forking

**Core Tools**:
1. **get_trial_balance** - Query with hierarchy support
2. **create_journal_entry** - Safe JE creation with validation + approval
3. **generate_bir_2307** - BIR 2307 DAT/XLSX generation

**Safety Controls**:
- Period lock validation
- Double-entry validation (0.01 tolerance)
- Draft by default (requires approval)
- Amount thresholds
- Audit log for all executions

**Deployment**:
```bash
# Dev (volume mount)
docker cp addons/ipai_mcp_finance odoo:/mnt/extra-addons/
docker exec odoo odoo -d mydb -u base -i ipai_mcp_finance --stop-after-init

# Prod (bake into image)
COPY addons/ipai_mcp_finance /mnt/extra-addons/ipai_mcp_finance
```

---

## 5. Acceptance Gates

**Must ALL pass for "done"**:

1. ✅ Odoo module installs without errors
2. ✅ All MCP tools registered and callable
3. ✅ Trial balance returns correct hierarchy
4. ✅ Journal entry validation blocks invalid entries
5. ✅ BIR 2307 generation produces valid DAT files
6. ✅ Audit log captures all tool executions
7. ✅ Security groups properly restrict access

---

## 6. SuperClaude Integration

**Auto-Activation**:
- "odoo" → odoo_developer + odoo18-oca-devops
- "BIR" → finance_ssc_expert + odoo-finance-automation
- "MCP" → odoo_developer + backend persona

**Skills Used**:
- `odoo-module-scaffold` - OCA-compliant module generation
- `odoo-finance-automation` - BIR tax filing automation
- `notion-integration-patterns` - Best practices (if applicable)

---

## 7. Repository Structure

```
mcp-projects/
├── CLAUDE.md                        # This file
├── README.md                        # Project documentation
├── addons/                          # Odoo modules
│   └── ipai_mcp_finance/           # Finance MCP tools
├── packages/db/sql/                # Supabase migrations
├── workflows/                       # n8n workflow definitions
├── infra/do/                       # DigitalOcean specs
├── scripts/                        # Automation scripts
├── docs/                           # Documentation
└── .github/workflows/              # CI/CD pipelines
```

---

## 8. Execution Persistence Policy

**Canonical rule**: Keep executing (plan → deploy → verify) until acceptance gates pass or a hard blocker occurs.

**Prohibited**:
- Asking user to manually run commands
- Producing "guides" instead of deploying
- Using Azure CLIs or services
- Using local Docker for production
