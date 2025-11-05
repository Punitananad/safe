#!/usr/bin/env python3
"""
Script to update flash messages to use the new toast system
Run this to standardize all flash messages across the application
"""

import os
import re
from pathlib import Path

# Define replacements for common flash messages
FLASH_REPLACEMENTS = {
    # Success messages
    r'flash\(["\']([^"\']*successfully[^"\']*)["\'],\s*["\']success["\']\)': r'toast_success("\1")',
    r'flash\(["\']([^"\']*saved[^"\']*)["\'],\s*["\']success["\']\)': r'toast_success(template_key="trade_saved")',
    r'flash\(["\']([^"\']*updated[^"\']*)["\'],\s*["\']success["\']\)': r'toast_success("\1")',
    r'flash\(["\']([^"\']*created[^"\']*)["\'],\s*["\']success["\']\)': r'toast_success("\1")',
    r'flash\(["\']([^"\']*deleted[^"\']*)["\'],\s*["\']success["\']\)': r'toast_success("\1")',
    
    # Error messages
    r'flash\(["\']([^"\']*error[^"\']*)["\'],\s*["\']error["\']\)': r'toast_error("\1")',
    r'flash\(["\']([^"\']*failed[^"\']*)["\'],\s*["\']error["\']\)': r'toast_error("\1")',
    r'flash\(["\']([^"\']*invalid[^"\']*)["\'],\s*["\']error["\']\)': r'toast_error("\1")',
    r'flash\(["\']([^"\']*not found[^"\']*)["\'],\s*["\']error["\']\)': r'toast_error("\1")',
    r'flash\(["\']([^"\']*required[^"\']*)["\'],\s*["\']error["\']\)': r'toast_error("\1")',
    
    # Warning messages
    r'flash\(["\']([^"\']*warning[^"\']*)["\'],\s*["\']warning["\']\)': r'toast_warning("\1")',
    r'flash\(["\']([^"\']*expired[^"\']*)["\'],\s*["\']warning["\']\)': r'toast_warning("\1")',
    
    # Info messages
    r'flash\(["\']([^"\']*sent[^"\']*)["\'],\s*["\']info["\']\)': r'toast_info("\1")',
    r'flash\(["\']([^"\']*logged out[^"\']*)["\'],\s*["\']info["\']\)': r'toast_success(template_key="logout_success")',
    
    # Generic flash without category (default to info)
    r'flash\(["\']([^"\']+)["\']\)': r'toast_info("\1")',
}

def update_file(file_path):
    """Update flash messages in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes_made = 0
        
        # Apply replacements
        for pattern, replacement in FLASH_REPLACEMENTS.items():
            new_content, count = re.subn(pattern, replacement, content, flags=re.IGNORECASE)
            if count > 0:
                content = new_content
                changes_made += count
                print(f"  - Applied {count} replacements for pattern: {pattern[:50]}...")
        
        # Only write if changes were made
        if changes_made > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated {file_path} ({changes_made} changes)")
            return True
        else:
            print(f"⏭️  No changes needed in {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating {file_path}: {e}")
        return False

def add_toast_import(file_path):
    """Add toast import to Python files that need it"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file uses toast functions but doesn't import them
        if ('toast_success(' in content or 'toast_error(' in content or 
            'toast_warning(' in content or 'toast_info(' in content):
            
            # Check if import already exists
            if 'from toast_utils import' not in content:
                # Find the right place to add import
                lines = content.split('\n')
                import_line = "from toast_utils import ToastManager, toast_success, toast_error, toast_warning, toast_info"
                
                # Find last import line
                last_import_idx = -1
                for i, line in enumerate(lines):
                    if line.strip().startswith('from ') or line.strip().startswith('import '):
                        last_import_idx = i
                
                if last_import_idx >= 0:
                    lines.insert(last_import_idx + 1, import_line)
                    content = '\n'.join(lines)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"✅ Added toast import to {file_path}")
                    return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error adding import to {file_path}: {e}")
        return False

def main():
    """Main function to update all Python files"""
    print("🚀 Starting flash message standardization...")
    
    # Get all Python files in the project
    python_files = []
    for root, dirs, files in os.walk('.'):
        # Skip certain directories
        if any(skip in root for skip in ['.git', '__pycache__', 'venv', 'env', 'node_modules']):
            continue
            
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"📁 Found {len(python_files)} Python files to check")
    
    updated_files = 0
    files_with_imports = 0
    
    for file_path in python_files:
        print(f"\n🔍 Checking {file_path}...")
        
        # Update flash messages
        if update_file(file_path):
            updated_files += 1
        
        # Add imports if needed
        if add_toast_import(file_path):
            files_with_imports += 1
    
    print(f"\n✨ Standardization complete!")
    print(f"📝 Updated {updated_files} files with new toast messages")
    print(f"📦 Added imports to {files_with_imports} files")
    print(f"\n🎯 Next steps:")
    print("1. Test the application to ensure all toasts work correctly")
    print("2. Remove any remaining manual flash message displays from templates")
    print("3. Verify toast service is loaded in all base templates")

if __name__ == "__main__":
    main()