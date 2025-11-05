#!/usr/bin/env python3
"""
Script to remove old flash message displays from templates
and ensure toast service is properly integrated
"""

import os
import re
from pathlib import Path

def clean_template_flash_messages(file_path):
    """Remove old flash message displays from templates"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes_made = 0
        
        # Patterns to remove old flash message displays
        patterns_to_remove = [
            # Bootstrap alert patterns
            r'{% with messages = get_flashed_messages\(with_categories=true\) %}.*?{% endwith %}',
            r'{% with messages = get_flashed_messages\(\) %}.*?{% endwith %}',
            
            # Individual flash message blocks
            r'<div[^>]*class="[^"]*flash[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*class="[^"]*alert[^"]*"[^>]*>.*?{{ message }}.*?</div>',
            
            # Flash message loops
            r'{% for category, message in messages %}.*?{% endfor %}',
            r'{% for message in messages %}.*?{% endfor %}',
        ]
        
        for pattern in patterns_to_remove:
            new_content, count = re.subn(pattern, '', content, flags=re.DOTALL | re.IGNORECASE)
            if count > 0:
                content = new_content
                changes_made += count
                print(f"  - Removed {count} flash message blocks")
        
        # Clean up extra whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        # Only write if changes were made
        if changes_made > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Cleaned {file_path} ({changes_made} changes)")
            return True
        else:
            print(f"⏭️  No flash messages to clean in {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error cleaning {file_path}: {e}")
        return False

def ensure_toast_service(file_path):
    """Ensure toast service is included in base templates"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if it's a base template
        if 'base' not in os.path.basename(file_path).lower():
            return False
        
        # Check if toast service is already included
        if 'toast-service.js' in content:
            print(f"✅ Toast service already included in {file_path}")
            return False
        
        # Add toast service before closing body tag
        toast_script = '''  <!-- Toast Service -->
  <script src="{{ url_for('static', filename='js/toast-service.js') }}"></script>
  
  <!-- Flash Messages Integration -->
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      <div id="flash-messages" style="display: none;">
        {% for category, message in messages %}
          <div data-flash-message data-flash-category="{{ category }}">{{ message }}</div>
        {% endfor %}
      </div>
    {% endif %}
  {% endwith %}'''
        
        # Insert before closing body tag
        if '</body>' in content:
            content = content.replace('</body>', f'{toast_script}\n</body>')
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Added toast service to {file_path}")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error updating {file_path}: {e}")
        return False

def main():
    """Main function to update all template files"""
    print("🚀 Starting template cleanup...")
    
    # Get all HTML template files
    template_files = []
    for root, dirs, files in os.walk('.'):
        # Skip certain directories
        if any(skip in root for skip in ['.git', '__pycache__', 'venv', 'env', 'node_modules']):
            continue
            
        for file in files:
            if file.endswith('.html'):
                template_files.append(os.path.join(root, file))
    
    print(f"📁 Found {len(template_files)} HTML template files to check")
    
    cleaned_files = 0
    updated_base_templates = 0
    
    for file_path in template_files:
        print(f"\n🔍 Checking {file_path}...")
        
        # Clean old flash messages
        if clean_template_flash_messages(file_path):
            cleaned_files += 1
        
        # Ensure toast service in base templates
        if ensure_toast_service(file_path):
            updated_base_templates += 1
    
    print(f"\n✨ Template cleanup complete!")
    print(f"🧹 Cleaned {cleaned_files} templates")
    print(f"📦 Updated {updated_base_templates} base templates with toast service")
    print(f"\n🎯 Next steps:")
    print("1. Test all pages to ensure toasts appear correctly")
    print("2. Check that no old flash messages are still showing")
    print("3. Verify toast positioning and styling on mobile devices")

if __name__ == "__main__":
    main()