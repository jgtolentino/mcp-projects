# -*- coding: utf-8 -*-
{
    'name': 'IPAI MCP Finance Tools',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Finance',
    'summary': 'Finance-specific MCP tools for AI-driven accounting operations',
    'description': """
IPAI MCP Finance Tools
======================

Extends mcp_server with finance-specific tools for InsightPulse AI:

**Tools Provided:**
- get_trial_balance: Retrieve trial balance with hierarchy support
- create_journal_entry: Safe JE creation with double-entry validation
- run_month_end_step: Orchestrated month-end closing workflow
- generate_bir_2307: Philippine BIR Form 2307 generation
- get_aging_report: AR/AP aging analysis

**Smart Delta Classification:** GAP_DELTA
- Inherits/extends mcp_server, does not replace
- Finance domain-specific logic only
- Follows OCA conventions

**Enterprise Features Matched:**
- SAP month-end closing workflows
- BIR compliance automation
- Multi-entity consolidation support
    """,
    'author': 'InsightPulse AI, TBWA Finance',
    'website': 'https://github.com/jgtolentino/insightpulse-odoo',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'account',
        'account_accountant',  # For period lock
        'mcp_server',          # Ivanov's base MCP module
    ],
    'external_dependencies': {
        'python': [],
        'bin': [],
    },
    'data': [
        'security/mcp_finance_security.xml',
        'security/ir.model.access.csv',
        'views/mcp_finance_config_views.xml',
        'data/mcp_finance_tools.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,  # Extension, not standalone app
    'auto_install': False,
    'development_status': 'Beta',
    'maintainers': ['jgtolentino'],
}
