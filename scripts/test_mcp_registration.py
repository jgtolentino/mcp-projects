#!/usr/bin/env python3
"""Test MCP tool registration in Odoo."""

import os
import sys
import xmlrpc.client


def test_mcp_registration():
    """Verify all MCP tools are registered."""
    url = os.getenv('ODOO_URL', 'http://localhost:8069')
    db = os.getenv('ODOO_DB', 'test_odoo')
    username = os.getenv('ODOO_USER', 'admin')
    password = os.getenv('ODOO_PASSWORD', 'admin')

    # Expected tools
    expected_tools = [
        'get_trial_balance',
        'create_journal_entry',
        'generate_bir_2307'
    ]

    try:
        # Connect to Odoo
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})

        if not uid:
            print("❌ Authentication failed")
            return False

        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

        # Search for registered tools
        tool_ids = models.execute_kw(
            db, uid, password,
            'mcp.finance.tool', 'search',
            [[['name', 'in', expected_tools]]]
        )

        if len(tool_ids) != len(expected_tools):
            print(f"❌ Expected {len(expected_tools)} tools, found {len(tool_ids)}")
            return False

        # Read tool details
        tools = models.execute_kw(
            db, uid, password,
            'mcp.finance.tool', 'read',
            [tool_ids, ['name', 'enabled']]
        )

        # Verify all tools are enabled
        for tool in tools:
            if not tool.get('enabled'):
                print(f"❌ Tool {tool['name']} is not enabled")
                return False
            print(f"✅ Tool registered and enabled: {tool['name']}")

        print(f"✅ All {len(expected_tools)} MCP tools registered successfully")
        return True

    except Exception as e:
        print(f"❌ Error testing MCP registration: {e}")
        return False


if __name__ == '__main__':
    success = test_mcp_registration()
    sys.exit(0 if success else 1)
