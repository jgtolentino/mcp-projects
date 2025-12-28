# -*- coding: utf-8 -*-
"""
Trial Balance MCP Tool
----------------------
Retrieves trial balance data with hierarchy support.

Tool: get_trial_balance
Category: Query (read-only, safe)

Parameters:
- company_id: int (optional, defaults to current)
- date_from: str (YYYY-MM-DD)
- date_to: str (YYYY-MM-DD)
- hierarchy: bool (include account hierarchy levels)
- account_types: list[str] (filter by account types)
- include_zero: bool (include zero-balance accounts)

Returns:
- Hierarchical trial balance with debit/credit/balance columns
- Account metadata (code, name, type, internal_group)
"""
from odoo import models, api
from odoo.exceptions import UserError, AccessError
from datetime import datetime, date
import logging
import time
import json

_logger = logging.getLogger(__name__)


class TrialBalanceTool(models.AbstractModel):
    """Trial Balance MCP Tool Implementation."""
    
    _name = 'mcp.finance.tool.trial_balance'
    _description = 'Trial Balance MCP Tool'

    @api.model
    def execute(self, params):
        """
        Execute trial balance query.
        
        Args:
            params: dict with keys:
                - company_id: int (optional)
                - date_from: str YYYY-MM-DD
                - date_to: str YYYY-MM-DD
                - hierarchy: bool (default True)
                - account_types: list[str] (optional filter)
                - include_zero: bool (default False)
        
        Returns:
            dict with:
                - success: bool
                - data: list of account rows
                - metadata: query metadata
        """
        start_time = time.time()
        
        try:
            # Validate and parse parameters
            company_id = params.get('company_id') or self.env.company.id
            company = self.env['res.company'].browse(company_id)
            if not company.exists():
                raise UserError(f"Company not found: {company_id}")
            
            # Check tool is enabled
            config = self.env['mcp.finance.config'].get_config(company_id)
            if not config.enable_trial_balance:
                raise AccessError("Trial Balance tool is disabled for this company")
            
            # Parse dates
            date_from = self._parse_date(params.get('date_from'))
            date_to = self._parse_date(params.get('date_to'))
            
            if not date_to:
                date_to = date.today()
            if not date_from:
                # Default to fiscal year start
                date_from = date(date_to.year, 1, 1)
            
            if date_from > date_to:
                raise UserError("date_from must be before date_to")
            
            hierarchy = params.get('hierarchy', True)
            account_types = params.get('account_types', [])
            include_zero = params.get('include_zero', False)
            
            # Build query
            result = self._get_trial_balance(
                company_id=company_id,
                date_from=date_from,
                date_to=date_to,
                hierarchy=hierarchy,
                account_types=account_types,
                include_zero=include_zero,
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log execution
            if config.log_all_queries:
                self.env['mcp.finance.tool.execution'].log_execution(
                    tool_name='get_trial_balance',
                    company_id=company_id,
                    parameters=params,
                    result={'row_count': len(result['accounts'])},
                    execution_time_ms=execution_time,
                )
            
            return {
                'success': True,
                'data': result,
                'metadata': {
                    'company': company.name,
                    'date_from': str(date_from),
                    'date_to': str(date_to),
                    'account_count': len(result['accounts']),
                    'execution_time_ms': execution_time,
                },
            }
            
        except Exception as e:
            _logger.exception(f"Trial balance tool error: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log failure
            self.env['mcp.finance.tool.execution'].log_execution(
                tool_name='get_trial_balance',
                company_id=params.get('company_id') or self.env.company.id,
                parameters=params,
                error=str(e),
                execution_time_ms=execution_time,
            )
            
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
            }

    def _parse_date(self, date_str):
        """Parse date string to date object."""
        if not date_str:
            return None
        if isinstance(date_str, date):
            return date_str
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise UserError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

    def _get_trial_balance(self, company_id, date_from, date_to, 
                           hierarchy=True, account_types=None, include_zero=False):
        """
        Build trial balance data.
        
        Uses account.move.line aggregation for accuracy.
        """
        Account = self.env['account.account']
        MoveLine = self.env['account.move.line']
        
        # Get accounts for company
        domain = [('company_ids', 'in', [company_id])]
        if account_types:
            domain.append(('account_type', 'in', account_types))
        
        accounts = Account.search(domain, order='code')
        
        # Get move line totals per account
        self.env.cr.execute("""
            SELECT 
                aml.account_id,
                COALESCE(SUM(aml.debit), 0) as total_debit,
                COALESCE(SUM(aml.credit), 0) as total_credit,
                COALESCE(SUM(aml.balance), 0) as balance
            FROM account_move_line aml
            JOIN account_move am ON aml.move_id = am.id
            WHERE aml.company_id = %s
              AND aml.date >= %s
              AND aml.date <= %s
              AND am.state = 'posted'
              AND aml.parent_state = 'posted'
            GROUP BY aml.account_id
        """, (company_id, date_from, date_to))
        
        totals_by_account = {
            row[0]: {
                'debit': float(row[1]),
                'credit': float(row[2]),
                'balance': float(row[3]),
            }
            for row in self.env.cr.fetchall()
        }
        
        # Build result rows
        rows = []
        totals = {'debit': 0.0, 'credit': 0.0, 'balance': 0.0}
        
        for account in accounts:
            amounts = totals_by_account.get(account.id, {
                'debit': 0.0, 'credit': 0.0, 'balance': 0.0
            })
            
            # Skip zero balances if not requested
            if not include_zero and amounts['balance'] == 0:
                continue
            
            row = {
                'account_id': account.id,
                'code': account.code,
                'name': account.name,
                'account_type': account.account_type,
                'internal_group': account.internal_group,
                'debit': amounts['debit'],
                'credit': amounts['credit'],
                'balance': amounts['balance'],
            }
            
            # Add hierarchy info
            if hierarchy:
                row['group_id'] = account.group_id.id if account.group_id else None
                row['group_name'] = account.group_id.name if account.group_id else None
                row['level'] = len(account.code.split('.')) if '.' in account.code else 1
            
            rows.append(row)
            
            totals['debit'] += amounts['debit']
            totals['credit'] += amounts['credit']
            totals['balance'] += amounts['balance']
        
        return {
            'accounts': rows,
            'totals': totals,
            'currency': self.env.company.currency_id.name,
        }

    @api.model
    def get_tool_schema(self):
        """Return MCP tool schema for registration."""
        return {
            'name': 'get_trial_balance',
            'description': 'Retrieve trial balance for a company with optional hierarchy and filters. Returns account codes, names, debit/credit totals, and running balances.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'company_id': {
                        'type': 'integer',
                        'description': 'Company ID (optional, defaults to current company)',
                    },
                    'date_from': {
                        'type': 'string',
                        'format': 'date',
                        'description': 'Start date (YYYY-MM-DD). Defaults to fiscal year start.',
                    },
                    'date_to': {
                        'type': 'string',
                        'format': 'date',
                        'description': 'End date (YYYY-MM-DD). Defaults to today.',
                    },
                    'hierarchy': {
                        'type': 'boolean',
                        'default': True,
                        'description': 'Include account hierarchy levels',
                    },
                    'account_types': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Filter by account types (asset, liability, equity, income, expense)',
                    },
                    'include_zero': {
                        'type': 'boolean',
                        'default': False,
                        'description': 'Include accounts with zero balance',
                    },
                },
                'required': [],
            },
        }
