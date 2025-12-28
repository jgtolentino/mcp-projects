# -*- coding: utf-8 -*-
"""
MCP Finance Configuration
-------------------------
Extends MCP server settings with finance-specific options.

Smart Delta: GAP_DELTA - extends mcp_server via _inherit
"""
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class McpFinanceConfig(models.Model):
    """Finance-specific MCP configuration settings."""
    
    _name = 'mcp.finance.config'
    _description = 'MCP Finance Configuration'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='cascade',
    )
    
    # === Tool Enablement ===
    enable_trial_balance = fields.Boolean(
        string='Enable Trial Balance Tool',
        default=True,
        help='Allow AI to query trial balance data',
    )
    enable_journal_entry = fields.Boolean(
        string='Enable Journal Entry Tool',
        default=False,
        help='Allow AI to create journal entries (requires approval)',
    )
    enable_month_end = fields.Boolean(
        string='Enable Month-End Tools',
        default=False,
        help='Allow AI to orchestrate month-end closing steps',
    )
    enable_bir_tools = fields.Boolean(
        string='Enable BIR Compliance Tools',
        default=True,
        help='Allow AI to generate BIR forms (2307, 2316, VAT)',
    )
    enable_aging_report = fields.Boolean(
        string='Enable Aging Report Tool',
        default=True,
        help='Allow AI to query AR/AP aging data',
    )
    
    # === Safety Controls ===
    require_approval_je = fields.Boolean(
        string='Require Approval for Journal Entries',
        default=True,
        help='AI-created journal entries are set to draft, require human approval',
    )
    max_je_amount = fields.Monetary(
        string='Max JE Amount Without Approval',
        default=0.0,
        currency_field='currency_id',
        help='JE amounts above this require escalated approval (0 = always require)',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    
    # === Audit Trail ===
    log_all_queries = fields.Boolean(
        string='Log All MCP Queries',
        default=True,
        help='Log every MCP finance tool invocation for audit trail',
    )
    
    _sql_constraints = [
        ('company_unique', 'UNIQUE(company_id)', 'Only one MCP Finance config per company'),
    ]

    @api.model
    def get_config(self, company_id=None):
        """Get or create finance config for company."""
        company_id = company_id or self.env.company.id
        config = self.search([('company_id', '=', company_id)], limit=1)
        if not config:
            config = self.create({'company_id': company_id})
            _logger.info(f"Created MCP Finance config for company {company_id}")
        return config


class ResConfigSettings(models.TransientModel):
    """Add MCP Finance settings to general settings."""
    
    _inherit = 'res.config.settings'

    mcp_finance_enable_trial_balance = fields.Boolean(
        related='company_id.mcp_finance_config_id.enable_trial_balance',
        readonly=False,
    )
    mcp_finance_enable_journal_entry = fields.Boolean(
        related='company_id.mcp_finance_config_id.enable_journal_entry',
        readonly=False,
    )
    mcp_finance_require_approval_je = fields.Boolean(
        related='company_id.mcp_finance_config_id.require_approval_je',
        readonly=False,
    )


class ResCompany(models.Model):
    """Add MCP Finance config link to company."""
    
    _inherit = 'res.company'

    mcp_finance_config_id = fields.Many2one(
        'mcp.finance.config',
        string='MCP Finance Config',
        compute='_compute_mcp_finance_config',
        store=True,
    )

    @api.depends('id')
    def _compute_mcp_finance_config(self):
        for company in self:
            config = self.env['mcp.finance.config'].search(
                [('company_id', '=', company.id)], limit=1
            )
            if not config:
                config = self.env['mcp.finance.config'].create({
                    'company_id': company.id
                })
            company.mcp_finance_config_id = config
