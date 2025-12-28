#!/usr/bin/env python3
"""Validate Odoo __manifest__.py file for OCA compliance."""

import sys
import ast


def validate_manifest(manifest_path):
    """Validate manifest file structure and required fields."""
    required_fields = [
        'name', 'version', 'category', 'license', 'author',
        'depends', 'data', 'installable'
    ]

    try:
        with open(manifest_path, 'r') as f:
            manifest_code = f.read()

        # Parse manifest as Python dict
        manifest = ast.literal_eval(manifest_code)

        # Check required fields
        missing_fields = [f for f in required_fields if f not in manifest]
        if missing_fields:
            print(f"❌ Missing required fields: {', '.join(missing_fields)}")
            return False

        # Check license is AGPL-3
        if manifest.get('license') != 'AGPL-3':
            print(f"❌ License must be AGPL-3, found: {manifest.get('license')}")
            return False

        # Check version format
        version = manifest.get('version', '')
        if not version.startswith('18.0.'):
            print(f"❌ Version must start with 18.0., found: {version}")
            return False

        # Check installable is True
        if not manifest.get('installable', False):
            print(f"❌ Module must be marked as installable")
            return False

        print("✅ Manifest validation passed")
        return True

    except FileNotFoundError:
        print(f"❌ Manifest file not found: {manifest_path}")
        return False
    except Exception as e:
        print(f"❌ Error parsing manifest: {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python validate_manifest.py <path_to___manifest__.py>")
        sys.exit(1)

    success = validate_manifest(sys.argv[1])
    sys.exit(0 if success else 1)
