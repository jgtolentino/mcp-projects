# -*- coding: utf-8 -*-
"""
MCP Finance Controller
----------------------
HTTP endpoints for finance-specific MCP tools.

Extends mcp_server controller with /mcp/finance/* endpoints.
"""
from odoo import http
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)


class McpFinanceController(http.Controller):
    """HTTP controller for MCP Finance tools."""

    def _json_response(self, data, status=200):
        """Return JSON response."""
        return Response(
            json.dumps(data, default=str),
            status=status,
            headers={'Content-Type': 'application/json'},
        )

    def _check_auth(self):
        """Check MCP authentication."""
        # Delegate to base MCP server auth
        # This checks API key from Authorization header
        auth_header = request.httprequest.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return None, "Missing or invalid Authorization header"
        
        api_key = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Validate against user API keys
        user = request.env['res.users'].sudo().search([
            ('api_key_ids.key', '=', api_key),
        ], limit=1)
        
        if not user:
            return None, "Invalid API key"
        
        return user, None

    @http.route('/mcp/finance/health', type='http', auth='none', 
                methods=['GET'], csrf=False)
    def health(self):
        """Health check endpoint."""
        return self._json_response({
            'status': 'healthy',
            'module': 'ipai_mcp_finance',
            'version': '18.0.1.0.0',
        })

    @http.route('/mcp/finance/tools', type='http', auth='none',
                methods=['GET'], csrf=False)
    def list_tools(self):
        """List available finance tools."""
        user, error = self._check_auth()
        if error:
            return self._json_response({'error': error}, status=401)
        
        tools = request.env['mcp.finance.tool'].sudo().with_user(user).list_available_tools()
        return self._json_response({'tools': tools})

    @http.route('/mcp/finance/tools/<string:tool_name>/schema', type='http',
                auth='none', methods=['GET'], csrf=False)
    def tool_schema(self, tool_name):
        """Get schema for a specific tool."""
        user, error = self._check_auth()
        if error:
            return self._json_response({'error': error}, status=401)
        
        # Map tool names to implementations
        tool_map = {
            'get_trial_balance': 'mcp.finance.tool.trial_balance',
            'create_journal_entry': 'mcp.finance.tool.journal_entry',
            'generate_bir_2307': 'mcp.finance.tool.bir_compliance',
        }
        
        if tool_name not in tool_map:
            return self._json_response(
                {'error': f'Unknown tool: {tool_name}'}, 
                status=404
            )
        
        tool = request.env[tool_map[tool_name]].sudo().with_user(user)
        schema = tool.get_tool_schema()
        
        return self._json_response({'schema': schema})

    @http.route('/mcp/finance/tools/<string:tool_name>/execute', type='json',
                auth='none', methods=['POST'], csrf=False)
    def execute_tool(self, tool_name):
        """Execute a finance tool."""
        user, error = self._check_auth()
        if error:
            return {'error': error}
        
        # Map tool names to implementations
        tool_map = {
            'get_trial_balance': 'mcp.finance.tool.trial_balance',
            'create_journal_entry': 'mcp.finance.tool.journal_entry',
            'generate_bir_2307': 'mcp.finance.tool.bir_compliance',
        }
        
        if tool_name not in tool_map:
            return {'error': f'Unknown tool: {tool_name}'}
        
        # Get parameters from request
        params = request.jsonrequest.get('params', {})
        
        # Execute tool
        tool = request.env[tool_map[tool_name]].sudo().with_user(user)
        result = tool.execute(params)
        
        return result

    @http.route('/mcp/finance/trial-balance', type='json',
                auth='none', methods=['POST'], csrf=False)
    def trial_balance(self):
        """Direct endpoint for trial balance."""
        user, error = self._check_auth()
        if error:
            return {'error': error}
        
        params = request.jsonrequest
        tool = request.env['mcp.finance.tool.trial_balance'].sudo().with_user(user)
        return tool.execute(params)

    @http.route('/mcp/finance/journal-entry', type='json',
                auth='none', methods=['POST'], csrf=False)
    def journal_entry(self):
        """Direct endpoint for journal entry creation."""
        user, error = self._check_auth()
        if error:
            return {'error': error}
        
        params = request.jsonrequest
        tool = request.env['mcp.finance.tool.journal_entry'].sudo().with_user(user)
        return tool.execute(params)

    @http.route('/mcp/finance/bir-2307', type='json',
                auth='none', methods=['POST'], csrf=False)
    def bir_2307(self):
        """Direct endpoint for BIR 2307 generation."""
        user, error = self._check_auth()
        if error:
            return {'error': error}
        
        params = request.jsonrequest
        tool = request.env['mcp.finance.tool.bir_compliance'].sudo().with_user(user)
        return tool.execute(params)

    @http.route('/mcp/finance/executions', type='http',
                auth='none', methods=['GET'], csrf=False)
    def list_executions(self):
        """List recent tool executions (audit log)."""
        user, error = self._check_auth()
        if error:
            return self._json_response({'error': error}, status=401)
        
        # Get query parameters
        limit = int(request.httprequest.args.get('limit', 50))
        tool_name = request.httprequest.args.get('tool')
        state = request.httprequest.args.get('state')
        
        domain = []
        if tool_name:
            tool = request.env['mcp.finance.tool'].search(
                [('technical_name', '=', tool_name)], limit=1
            )
            if tool:
                domain.append(('tool_id', '=', tool.id))
        
        if state:
            domain.append(('state', '=', state))
        
        executions = request.env['mcp.finance.tool.execution'].sudo().with_user(user).search(
            domain, limit=limit, order='create_date desc'
        )
        
        data = []
        for ex in executions:
            data.append({
                'id': ex.id,
                'tool': ex.tool_id.technical_name,
                'state': ex.state,
                'user': ex.user_id.name,
                'created': ex.create_date.isoformat(),
                'execution_time_ms': ex.execution_time_ms,
                'error': ex.error_message,
            })
        
        return self._json_response({'executions': data})
