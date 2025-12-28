# -*- coding: utf-8 -*-
"""
BIR Compliance MCP Tool
-----------------------
Philippine BIR form generation (2307, 2316, VAT returns).

Tool: generate_bir_2307
Category: Compliance

Parameters:
- company_id: int (optional)
- period: str (YYYY-QN format, e.g., 2025-Q4)
- vendor_ids: list[int] (optional, all if not specified)
- output_format: str (dat, xlsx, pdf)

BIR Form 2307: Certificate of Creditable Tax Withheld at Source
- Required for vendor payments with withholding tax
- Due: Within 10 days after end of quarter
"""
from odoo import models, api, _
from odoo.exceptions import UserError, AccessError
from datetime import datetime, date
import logging
import time
import json
import io

_logger = logging.getLogger(__name__)


class BirComplianceTool(models.AbstractModel):
    """BIR Compliance MCP Tool Implementation."""
    
    _name = 'mcp.finance.tool.bir_compliance'
    _description = 'BIR Compliance MCP Tool'

    # BIR 2307 field positions for DAT format
    BIR_2307_FIELDS = [
        ('returning_period', 6),      # MMYYYY
        ('seq_no', 10),               # Sequence number
        ('tin', 9),                   # Vendor TIN (9 digits)
        ('branch_code', 4),           # Branch code
        ('vendor_name', 50),          # Vendor name
        ('vendor_address', 100),      # Vendor address
        ('atc', 5),                   # Alpha Tax Code
        ('tax_rate', 5),              # Tax rate (5.2 format)
        ('income_payment', 14),       # Income payment amount
        ('tax_withheld', 14),         # Tax withheld amount
    ]

    @api.model
    def execute(self, params):
        """
        Execute BIR 2307 generation.
        
        Args:
            params: dict with keys:
                - company_id: int (optional)
                - period: str YYYY-QN (required)
                - vendor_ids: list[int] (optional)
                - output_format: str dat|xlsx|pdf (default dat)
        
        Returns:
            dict with:
                - success: bool
                - file_content: base64 encoded file
                - filename: str
                - record_count: int
                - total_base: float
                - total_tax: float
        """
        start_time = time.time()
        
        try:
            company_id = params.get('company_id') or self.env.company.id
            company = self.env['res.company'].browse(company_id)
            if not company.exists():
                raise UserError(f"Company not found: {company_id}")
            
            # Check tool is enabled
            config = self.env['mcp.finance.config'].get_config(company_id)
            if not config.enable_bir_tools:
                raise AccessError("BIR Compliance tools are disabled for this company")
            
            # Parse period
            period = params.get('period')
            if not period:
                raise UserError("period is required (YYYY-QN format, e.g., 2025-Q4)")
            
            date_from, date_to = self._parse_quarter(period)
            
            vendor_ids = params.get('vendor_ids')
            output_format = params.get('output_format', 'dat').lower()
            
            if output_format not in ('dat', 'xlsx', 'pdf'):
                raise UserError(f"Invalid output_format: {output_format}. Use dat, xlsx, or pdf")
            
            # Get withholding tax data
            data = self._get_withholding_data(
                company_id=company_id,
                date_from=date_from,
                date_to=date_to,
                vendor_ids=vendor_ids,
            )
            
            # Generate output
            if output_format == 'dat':
                content, filename = self._generate_dat(data, period, company)
            elif output_format == 'xlsx':
                content, filename = self._generate_xlsx(data, period, company)
            else:
                content, filename = self._generate_pdf(data, period, company)
            
            import base64
            file_content = base64.b64encode(content).decode('utf-8')
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log execution
            self.env['mcp.finance.tool.execution'].log_execution(
                tool_name='generate_bir_2307',
                company_id=company_id,
                parameters=params,
                result={
                    'record_count': len(data['records']),
                    'total_base': data['totals']['base'],
                    'total_tax': data['totals']['tax'],
                },
                execution_time_ms=execution_time,
            )
            
            return {
                'success': True,
                'file_content': file_content,
                'filename': filename,
                'record_count': len(data['records']),
                'total_base': data['totals']['base'],
                'total_tax': data['totals']['tax'],
                'metadata': {
                    'company': company.name,
                    'period': period,
                    'output_format': output_format,
                    'execution_time_ms': execution_time,
                },
            }
            
        except Exception as e:
            _logger.exception(f"BIR 2307 tool error: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            
            self.env['mcp.finance.tool.execution'].log_execution(
                tool_name='generate_bir_2307',
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

    def _parse_quarter(self, period):
        """Parse YYYY-QN to date range."""
        try:
            year, quarter = period.split('-Q')
            year = int(year)
            quarter = int(quarter)
            
            if quarter < 1 or quarter > 4:
                raise ValueError("Quarter must be 1-4")
            
            # Quarter start/end dates
            quarter_months = {
                1: (1, 3),
                2: (4, 6),
                3: (7, 9),
                4: (10, 12),
            }
            start_month, end_month = quarter_months[quarter]
            
            date_from = date(year, start_month, 1)
            
            # End of quarter
            if end_month == 12:
                date_to = date(year, 12, 31)
            else:
                import calendar
                last_day = calendar.monthrange(year, end_month)[1]
                date_to = date(year, end_month, last_day)
            
            return date_from, date_to
            
        except Exception:
            raise UserError(f"Invalid period format: {period}. Use YYYY-QN (e.g., 2025-Q4)")

    def _get_withholding_data(self, company_id, date_from, date_to, vendor_ids=None):
        """
        Get withholding tax data from vendor bills.
        
        Looks for bills with withholding tax lines (typically negative tax amounts
        or specific tax accounts configured for withholding).
        """
        domain = [
            ('company_id', '=', company_id),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ]
        
        if vendor_ids:
            domain.append(('partner_id', 'in', vendor_ids))
        
        bills = self.env['account.move'].search(domain)
        
        records = []
        totals = {'base': 0.0, 'tax': 0.0}
        
        for bill in bills:
            # Find withholding tax lines
            # This is simplified - real implementation would look for specific tax codes
            wht_lines = bill.line_ids.filtered(
                lambda l: l.tax_line_id and 
                l.tax_line_id.description and 
                'withholding' in l.tax_line_id.description.lower()
            )
            
            if not wht_lines:
                # Also check for EWT (Expanded Withholding Tax) codes
                wht_lines = bill.line_ids.filtered(
                    lambda l: l.tax_line_id and 
                    l.tax_line_id.name and 
                    ('EWT' in l.tax_line_id.name or 'WC' in l.tax_line_id.name)
                )
            
            for wht_line in wht_lines:
                partner = bill.partner_id
                
                # Get base amount (the income payment)
                # For withholding, we need to calculate back from the tax
                tax = wht_line.tax_line_id
                tax_rate = abs(tax.amount) if tax else 0
                tax_amount = abs(wht_line.balance)
                
                if tax_rate > 0:
                    base_amount = (tax_amount / tax_rate) * 100
                else:
                    base_amount = 0
                
                record = {
                    'vendor_tin': partner.vat or '',
                    'vendor_name': partner.name or '',
                    'vendor_address': self._format_address(partner),
                    'atc': self._get_atc(tax),
                    'tax_rate': tax_rate,
                    'base_amount': base_amount,
                    'tax_amount': tax_amount,
                    'bill_ref': bill.name,
                    'bill_date': bill.invoice_date,
                }
                records.append(record)
                
                totals['base'] += base_amount
                totals['tax'] += tax_amount
        
        return {
            'records': records,
            'totals': totals,
        }

    def _format_address(self, partner):
        """Format partner address for BIR."""
        parts = [
            partner.street or '',
            partner.street2 or '',
            partner.city or '',
            partner.state_id.name if partner.state_id else '',
            partner.zip or '',
        ]
        return ', '.join(p for p in parts if p)[:100]

    def _get_atc(self, tax):
        """Get Alpha Tax Code for withholding tax."""
        # Map tax codes to BIR ATC codes
        # This is simplified - real implementation would use tax configuration
        if not tax:
            return 'WC010'  # Default
        
        name = (tax.name or '').upper()
        if 'PROFESSIONAL' in name or 'WC010' in name:
            return 'WC010'
        elif 'RENTAL' in name or 'WC020' in name:
            return 'WC020'
        elif 'SERVICE' in name or 'WC100' in name:
            return 'WC100'
        elif 'GOODS' in name or 'WC120' in name:
            return 'WC120'
        
        return 'WC010'  # Default to professional fees

    def _generate_dat(self, data, period, company):
        """Generate BIR DAT file format."""
        lines = []
        
        # Parse period for header
        year, quarter = period.split('-Q')
        # Use last month of quarter
        quarter_end_month = int(quarter) * 3
        returning_period = f"{quarter_end_month:02d}{year}"
        
        for seq, record in enumerate(data['records'], 1):
            # Format TIN (remove dashes, pad to 9 chars)
            tin = (record['vendor_tin'] or '').replace('-', '')[:9].ljust(9)
            
            # Format amounts (14 chars, 2 decimal places, right-aligned)
            base = f"{record['base_amount']:014.2f}".replace('.', '')
            tax = f"{record['tax_amount']:014.2f}".replace('.', '')
            
            # Build line
            line = (
                f"{returning_period:6s}"
                f"{seq:010d}"
                f"{tin:9s}"
                f"{'0000':4s}"  # Branch code
                f"{record['vendor_name'][:50]:50s}"
                f"{record['vendor_address'][:100]:100s}"
                f"{record['atc']:5s}"
                f"{record['tax_rate']:05.2f}"
                f"{base:14s}"
                f"{tax:14s}"
            )
            lines.append(line)
        
        content = '\r\n'.join(lines).encode('utf-8')
        filename = f"BIR2307_{company.vat or 'TIN'}_{period}.dat"
        
        return content, filename

    def _generate_xlsx(self, data, period, company):
        """Generate Excel format with headers."""
        try:
            import xlsxwriter
        except ImportError:
            raise UserError("xlsxwriter library required for Excel export")
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('BIR 2307')
        
        # Headers
        headers = [
            'Seq', 'Vendor TIN', 'Vendor Name', 'Address',
            'ATC', 'Tax Rate', 'Base Amount', 'Tax Withheld',
            'Bill Reference', 'Bill Date'
        ]
        
        header_format = workbook.add_format({'bold': True, 'bg_color': '#CCCCCC'})
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data rows
        for row, record in enumerate(data['records'], 1):
            worksheet.write(row, 0, row)
            worksheet.write(row, 1, record['vendor_tin'])
            worksheet.write(row, 2, record['vendor_name'])
            worksheet.write(row, 3, record['vendor_address'])
            worksheet.write(row, 4, record['atc'])
            worksheet.write(row, 5, record['tax_rate'])
            worksheet.write(row, 6, record['base_amount'], money_format)
            worksheet.write(row, 7, record['tax_amount'], money_format)
            worksheet.write(row, 8, record['bill_ref'])
            worksheet.write(row, 9, record['bill_date'], date_format)
        
        # Totals
        total_row = len(data['records']) + 2
        worksheet.write(total_row, 5, 'TOTALS:', header_format)
        worksheet.write(total_row, 6, data['totals']['base'], money_format)
        worksheet.write(total_row, 7, data['totals']['tax'], money_format)
        
        workbook.close()
        content = output.getvalue()
        filename = f"BIR2307_{company.vat or 'TIN'}_{period}.xlsx"
        
        return content, filename

    def _generate_pdf(self, data, period, company):
        """Generate PDF format (stub - would use report engine)."""
        # For now, return Excel - PDF would use QWeb report
        _logger.warning("PDF generation not yet implemented, returning XLSX")
        return self._generate_xlsx(data, period, company)

    @api.model
    def get_tool_schema(self):
        """Return MCP tool schema for registration."""
        return {
            'name': 'generate_bir_2307',
            'description': 'Generate Philippine BIR Form 2307 (Certificate of Creditable Tax Withheld at Source) for vendor payments with withholding tax.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'company_id': {
                        'type': 'integer',
                        'description': 'Company ID (optional, defaults to current company)',
                    },
                    'period': {
                        'type': 'string',
                        'pattern': '^\\d{4}-Q[1-4]$',
                        'description': 'Reporting period in YYYY-QN format (e.g., 2025-Q4)',
                    },
                    'vendor_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'Filter to specific vendor IDs (optional, all if not specified)',
                    },
                    'output_format': {
                        'type': 'string',
                        'enum': ['dat', 'xlsx', 'pdf'],
                        'default': 'dat',
                        'description': 'Output format: dat (BIR upload), xlsx (Excel), pdf',
                    },
                },
                'required': ['period'],
            },
        }
