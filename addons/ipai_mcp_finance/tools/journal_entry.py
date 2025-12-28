# -*- coding: utf-8 -*-
"""
Journal Entry MCP Tool
----------------------
Safe journal entry creation with double-entry validation.

Tool: create_journal_entry
Category: Create (requires approval by default)

Parameters:
- company_id: int (optional)
- journal_code: str (e.g., 'MISC', 'BANK', 'CASH')
- date: str (YYYY-MM-DD)
- ref: str (reference/memo)
- lines: list of {account, debit, credit, partner, analytic}
- auto_post: bool (default False - stays in draft)

Safety Controls:
- Double-entry validation (debits must equal credits)
- Account existence validation
- Period lock check
- Optional approval workflow
- Audit trail logging
"""
from odoo import models, api, _
from odoo.exceptions import UserError, AccessError, ValidationError
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
import logging
import time
import json

_logger = logging.getLogger(__name__)

# Tolerance for floating point comparison
BALANCE_TOLERANCE = 0.01


class JournalEntryTool(models.AbstractModel):
    """Journal Entry MCP Tool Implementation."""
    
    _name = 'mcp.finance.tool.journal_entry'
    _description = 'Journal Entry MCP Tool'

    @api.model
    def execute(self, params):
        """
        Execute journal entry creation.
        
        Args:
            params: dict with keys:
                - company_id: int (optional)
                - journal_code: str (required)
                - date: str YYYY-MM-DD (required)
                - ref: str (required)
                - lines: list of line dicts (required)
                - auto_post: bool (default False)
        
        Returns:
            dict with:
                - success: bool
                - move_id: int (created move ID)
                - move_name: str (sequence number)
                - state: str (draft/posted)
                - requires_approval: bool
        """
        start_time = time.time()
        
        try:
            # Validate parameters
            company_id = params.get('company_id') or self.env.company.id
            company = self.env['res.company'].browse(company_id)
            if not company.exists():
                raise UserError(f"Company not found: {company_id}")
            
            # Check tool is enabled
            config = self.env['mcp.finance.config'].get_config(company_id)
            if not config.enable_journal_entry:
                raise AccessError("Journal Entry tool is disabled for this company")
            
            # Validate required fields
            journal_code = params.get('journal_code')
            if not journal_code:
                raise UserError("journal_code is required")
            
            je_date = self._parse_date(params.get('date'))
            if not je_date:
                raise UserError("date is required (YYYY-MM-DD)")
            
            ref = params.get('ref')
            if not ref:
                raise UserError("ref (reference/memo) is required")
            
            lines = params.get('lines')
            if not lines or not isinstance(lines, list):
                raise UserError("lines is required and must be a list")
            
            auto_post = params.get('auto_post', False)
            
            # Check period lock
            self._check_period_lock(company_id, je_date)
            
            # Find journal
            journal = self.env['account.journal'].search([
                ('code', '=', journal_code),
                ('company_id', '=', company_id),
            ], limit=1)
            if not journal:
                raise UserError(f"Journal not found: {journal_code}")
            
            # Validate and build lines
            move_lines = self._build_move_lines(lines, company_id)
            
            # Check balance
            self._validate_balance(move_lines)
            
            # Calculate total for approval threshold
            total_amount = sum(line.get('debit', 0) for line in move_lines)
            
            # Determine if approval required
            requires_approval = False
            if config.require_approval_je:
                requires_approval = True
            if config.max_je_amount > 0 and total_amount > config.max_je_amount:
                requires_approval = True
            
            # Force draft if approval required
            if requires_approval:
                auto_post = False
            
            # Create move
            move_vals = {
                'company_id': company_id,
                'journal_id': journal.id,
                'date': je_date,
                'ref': ref,
                'line_ids': [(0, 0, line) for line in move_lines],
                'move_type': 'entry',
            }
            
            move = self.env['account.move'].with_company(company_id).create(move_vals)
            
            # Auto-post if allowed
            if auto_post and not requires_approval:
                move.action_post()
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log execution
            state = 'pending' if requires_approval else 'executed'
            self.env['mcp.finance.tool.execution'].log_execution(
                tool_name='create_journal_entry',
                company_id=company_id,
                parameters=params,
                result={
                    'move_id': move.id,
                    'move_name': move.name,
                    'total_amount': total_amount,
                },
                execution_time_ms=execution_time,
                state=state,
            )
            
            return {
                'success': True,
                'move_id': move.id,
                'move_name': move.name,
                'state': move.state,
                'requires_approval': requires_approval,
                'total_amount': total_amount,
                'metadata': {
                    'company': company.name,
                    'journal': journal.name,
                    'line_count': len(move_lines),
                    'execution_time_ms': execution_time,
                },
            }
            
        except Exception as e:
            _logger.exception(f"Journal entry tool error: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            
            self.env['mcp.finance.tool.execution'].log_execution(
                tool_name='create_journal_entry',
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

    def _check_period_lock(self, company_id, je_date):
        """Check if the period is locked."""
        company = self.env['res.company'].browse(company_id)
        
        # Check fiscal year lock
        if company.fiscalyear_lock_date and je_date <= company.fiscalyear_lock_date:
            raise UserError(
                f"Period is locked. Fiscal year lock date: {company.fiscalyear_lock_date}"
            )
        
        # Check period lock for non-advisers
        if company.period_lock_date and je_date <= company.period_lock_date:
            if not self.env.user.has_group('account.group_account_manager'):
                raise UserError(
                    f"Period is locked for non-advisers. Lock date: {company.period_lock_date}"
                )

    def _build_move_lines(self, lines, company_id):
        """Build and validate move line values."""
        Account = self.env['account.account']
        Partner = self.env['res.partner']
        
        move_lines = []
        
        for i, line in enumerate(lines):
            # Validate account
            account_ref = line.get('account')
            if not account_ref:
                raise UserError(f"Line {i+1}: account is required")
            
            # Account can be code or ID
            if isinstance(account_ref, int):
                account = Account.browse(account_ref)
            else:
                account = Account.search([
                    ('code', '=', account_ref),
                    ('company_ids', 'in', [company_id]),
                ], limit=1)
            
            if not account.exists():
                raise UserError(f"Line {i+1}: account not found: {account_ref}")
            
            # Get amounts
            debit = float(line.get('debit', 0))
            credit = float(line.get('credit', 0))
            
            if debit < 0 or credit < 0:
                raise UserError(f"Line {i+1}: debit and credit must be non-negative")
            
            if debit > 0 and credit > 0:
                raise UserError(f"Line {i+1}: cannot have both debit and credit on same line")
            
            if debit == 0 and credit == 0:
                raise UserError(f"Line {i+1}: must have either debit or credit amount")
            
            # Build line
            move_line = {
                'account_id': account.id,
                'name': line.get('name') or line.get('label') or '/',
                'debit': debit,
                'credit': credit,
            }
            
            # Optional partner
            partner_ref = line.get('partner')
            if partner_ref:
                if isinstance(partner_ref, int):
                    partner = Partner.browse(partner_ref)
                else:
                    partner = Partner.search([
                        '|',
                        ('ref', '=', partner_ref),
                        ('name', 'ilike', partner_ref),
                    ], limit=1)
                
                if partner.exists():
                    move_line['partner_id'] = partner.id
            
            # Optional analytic
            analytic = line.get('analytic')
            if analytic:
                # Analytic distribution in Odoo 18 is a dict
                if isinstance(analytic, dict):
                    move_line['analytic_distribution'] = analytic
                elif isinstance(analytic, int):
                    move_line['analytic_distribution'] = {str(analytic): 100}
            
            move_lines.append(move_line)
        
        return move_lines

    def _validate_balance(self, move_lines):
        """Validate that debits equal credits."""
        total_debit = sum(line.get('debit', 0) for line in move_lines)
        total_credit = sum(line.get('credit', 0) for line in move_lines)
        
        diff = abs(total_debit - total_credit)
        if diff > BALANCE_TOLERANCE:
            raise ValidationError(
                f"Journal entry is not balanced. "
                f"Total debit: {total_debit:.2f}, Total credit: {total_credit:.2f}, "
                f"Difference: {diff:.2f}"
            )

    @api.model
    def get_tool_schema(self):
        """Return MCP tool schema for registration."""
        return {
            'name': 'create_journal_entry',
            'description': 'Create a journal entry with double-entry validation. By default, entries are created in draft state and require human approval.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'company_id': {
                        'type': 'integer',
                        'description': 'Company ID (optional, defaults to current company)',
                    },
                    'journal_code': {
                        'type': 'string',
                        'description': 'Journal code (e.g., MISC, BANK, CASH, STJ)',
                    },
                    'date': {
                        'type': 'string',
                        'format': 'date',
                        'description': 'Journal entry date (YYYY-MM-DD)',
                    },
                    'ref': {
                        'type': 'string',
                        'description': 'Reference/memo for the entry',
                    },
                    'lines': {
                        'type': 'array',
                        'description': 'Journal entry lines (debits must equal credits)',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'account': {
                                    'type': ['string', 'integer'],
                                    'description': 'Account code or ID',
                                },
                                'debit': {
                                    'type': 'number',
                                    'description': 'Debit amount (0 if credit line)',
                                },
                                'credit': {
                                    'type': 'number',
                                    'description': 'Credit amount (0 if debit line)',
                                },
                                'name': {
                                    'type': 'string',
                                    'description': 'Line description/label',
                                },
                                'partner': {
                                    'type': ['string', 'integer'],
                                    'description': 'Partner reference or ID (optional)',
                                },
                                'analytic': {
                                    'type': ['object', 'integer'],
                                    'description': 'Analytic distribution or account ID',
                                },
                            },
                            'required': ['account'],
                        },
                    },
                    'auto_post': {
                        'type': 'boolean',
                        'default': False,
                        'description': 'Auto-post the entry (only if approval not required)',
                    },
                },
                'required': ['journal_code', 'date', 'ref', 'lines'],
            },
        }
