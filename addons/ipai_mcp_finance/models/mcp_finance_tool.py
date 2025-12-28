# -*- coding: utf-8 -*-
"""
MCP Finance Tool Registration
-----------------------------
Registers finance-specific tools with the MCP server.

This extends mcp_server's tool registry with accounting operations.
"""
from odoo import models, fields, api
from odoo.exceptions import UserError, AccessError
import json
import logging
from datetime import date, datetime
from decimal import Decimal

_logger = logging.getLogger(__name__)


class McpFinanceTool(models.Model):
    """Registry for MCP Finance tools."""
    
    _name = 'mcp.finance.tool'
    _description = 'MCP Finance Tool'
    _order = 'sequence, name'

    name = fields.Char(string='Tool Name', required=True)
    technical_name = fields.Char(string='Technical Name', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    category = fields.Selection([
        ('query', 'Query/Read'),
        ('create', 'Create'),
        ('workflow', 'Workflow'),
        ('compliance', 'Compliance'),
    ], string='Category', required=True, default='query')
    
    requires_approval = fields.Boolean(
        string='Requires Approval',
        default=False,
        help='Operations from this tool require human approval',
    )
    
    # JSON schema for tool parameters
    parameter_schema = fields.Text(
        string='Parameter Schema (JSON)',
        help='JSON Schema defining tool input parameters',
    )

    _sql_constraints = [
        ('technical_name_unique', 'UNIQUE(technical_name)', 'Technical name must be unique'),
    ]

    @api.model
    def get_tool_schema(self, technical_name):
        """Return tool schema for MCP protocol."""
        tool = self.search([('technical_name', '=', technical_name)], limit=1)
        if not tool:
            raise UserError(f"Tool not found: {technical_name}")
        
        return {
            'name': tool.technical_name,
            'description': tool.description,
            'inputSchema': json.loads(tool.parameter_schema) if tool.parameter_schema else {},
        }

    @api.model
    def list_available_tools(self, company_id=None):
        """List all tools available for the company."""
        config = self.env['mcp.finance.config'].get_config(company_id)
        tools = self.search([('active', '=', True)])
        
        available = []
        for tool in tools:
            # Check if tool is enabled in config
            config_field = f"enable_{tool.technical_name.replace('get_', '').replace('create_', '').replace('run_', '').replace('generate_', '')}"
            if hasattr(config, config_field) and not getattr(config, config_field, True):
                continue
            available.append({
                'name': tool.technical_name,
                'description': tool.description,
                'category': tool.category,
                'requires_approval': tool.requires_approval,
            })
        
        return available


class McpFinanceToolExecution(models.Model):
    """Audit log for MCP Finance tool executions."""
    
    _name = 'mcp.finance.tool.execution'
    _description = 'MCP Finance Tool Execution Log'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    tool_id = fields.Many2one('mcp.finance.tool', string='Tool', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    
    parameters = fields.Text(string='Input Parameters (JSON)')
    result = fields.Text(string='Result (JSON)')
    
    state = fields.Selection([
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('executed', 'Executed'),
        ('rejected', 'Rejected'),
        ('failed', 'Failed'),
    ], string='State', default='executed')
    
    error_message = fields.Text(string='Error Message')
    execution_time_ms = fields.Integer(string='Execution Time (ms)')
    
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('tool_id', 'create_date')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.tool_id.technical_name} @ {record.create_date}"

    @api.model
    def log_execution(self, tool_name, company_id, parameters, result=None, 
                      error=None, execution_time_ms=0, state='executed'):
        """Create execution log entry."""
        tool = self.env['mcp.finance.tool'].search(
            [('technical_name', '=', tool_name)], limit=1
        )
        if not tool:
            _logger.warning(f"Logging execution for unknown tool: {tool_name}")
            return None
        
        return self.create({
            'tool_id': tool.id,
            'company_id': company_id,
            'parameters': json.dumps(parameters) if parameters else None,
            'result': json.dumps(result, default=str) if result else None,
            'error_message': error,
            'execution_time_ms': execution_time_ms,
            'state': 'failed' if error else state,
        })
