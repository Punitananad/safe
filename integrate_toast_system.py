#!/usr/bin/env python3
"""
Master script to integrate the centralized toast system
This script coordinates all the updates needed for toast standardization
"""

import os
import sys
import subprocess
from pathlib import Path

def run_script(script_name, description):
    """Run a Python script and handle errors"""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=True, text=True, cwd='.')
        
        if result.returncode == 0:
            print(result.stdout)
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error running {script_name}: {e}")
        return False

def verify_files_exist():
    """Verify all required files exist"""
    required_files = [
        'static/js/toast-service.js',
        'toast_utils.py',
        'update_flash_messages.py',
        'update_templates.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        return False
    
    print("✅ All required files exist")
    return True

def create_backup():
    """Create backup of important files before modification"""
    import shutil
    from datetime import datetime
    
    backup_dir = f"backup_toast_integration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup key files
        files_to_backup = ['app.py', 'journal.py']
        
        for file_path in files_to_backup:
            if os.path.exists(file_path):
                shutil.copy2(file_path, os.path.join(backup_dir, file_path))
        
        # Backup templates directory
        if os.path.exists('templates'):
            shutil.copytree('templates', os.path.join(backup_dir, 'templates'))
        
        print(f"✅ Backup created in {backup_dir}")
        return backup_dir
        
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return None

def update_app_context_processor():
    """Add toast context processor to app.py"""
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if context processor already exists
        if '@app.context_processor' in content and 'toast_context_processor' in content:
            print("✅ Toast context processor already exists")
            return True
        
        # Add context processor before the blueprint registration
        context_processor_code = '''
# Add toast context processor
@app.context_processor
def inject_toast_utils():
    """Make toast utilities available in all templates"""
    from toast_utils import toast_context_processor
    return toast_context_processor()
'''
        
        # Find a good place to insert (before blueprint registration)
        if '# Register Blueprints' in content:
            content = content.replace('# Register Blueprints', 
                                    f'{context_processor_code}\n# Register Blueprints')
        else:
            # Insert before the last few lines
            lines = content.split('\n')
            insert_pos = len(lines) - 10  # Insert near the end
            lines.insert(insert_pos, context_processor_code)
            content = '\n'.join(lines)
        
        with open('app.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Added toast context processor to app.py")
        return True
        
    except Exception as e:
        print(f"❌ Error updating app.py context processor: {e}")
        return False

def main():
    """Main integration function"""
    print("🎯 CalculateNTrade Toast System Integration")
    print("=" * 60)
    print("This script will standardize all toast notifications across the application")
    print("and remove inconsistent flash message implementations.")
    print()
    
    # Verify prerequisites
    if not verify_files_exist():
        print("❌ Prerequisites not met. Please ensure all required files exist.")
        return False
    
    # Create backup
    backup_dir = create_backup()
    if not backup_dir:
        print("⚠️  Continuing without backup (not recommended)")
    
    success_count = 0
    total_steps = 4
    
    # Step 1: Update Python files to use toast system
    if run_script('update_flash_messages.py', 'Updating Python files to use toast system'):
        success_count += 1
    
    # Step 2: Clean up template flash messages
    if run_script('update_templates.py', 'Cleaning up template flash message displays'):
        success_count += 1
    
    # Step 3: Add context processor
    if update_app_context_processor():
        success_count += 1
    
    # Step 4: Verify integration
    print(f"\n{'='*60}")
    print("🔍 Verifying Integration")
    print(f"{'='*60}")
    
    verification_passed = True
    
    # Check if toast service exists
    if os.path.exists('static/js/toast-service.js'):
        print("✅ Toast service JavaScript file exists")
    else:
        print("❌ Toast service JavaScript file missing")
        verification_passed = False
    
    # Check if toast utils exists
    if os.path.exists('toast_utils.py'):
        print("✅ Toast utilities Python module exists")
    else:
        print("❌ Toast utilities Python module missing")
        verification_passed = False
    
    # Check base templates for toast service inclusion
    base_templates = ['templates/base.html', 'templates/simple_base.html', 'templates/base_new_journal.html']
    for template in base_templates:
        if os.path.exists(template):
            with open(template, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'toast-service.js' in content:
                print(f"✅ Toast service included in {template}")
            else:
                print(f"⚠️  Toast service not found in {template}")
        else:
            print(f"⚠️  Template {template} not found")
    
    if verification_passed:
        success_count += 1
    
    # Final summary
    print(f"\n{'='*60}")
    print("📊 Integration Summary")
    print(f"{'='*60}")
    print(f"✅ Completed steps: {success_count}/{total_steps}")
    
    if success_count == total_steps:
        print("🎉 Toast system integration completed successfully!")
        print("\n🎯 Next steps:")
        print("1. Start your Flask application")
        print("2. Test various user actions to see toast notifications")
        print("3. Check browser console for any JavaScript errors")
        print("4. Verify toast positioning on mobile devices")
        print("5. Test deduplication by triggering the same action multiple times")
        
        if backup_dir:
            print(f"\n💾 Backup available at: {backup_dir}")
            print("   You can restore from backup if needed")
        
        return True
    else:
        print("⚠️  Integration completed with some issues")
        print("   Please review the errors above and fix them manually")
        
        if backup_dir:
            print(f"\n💾 Backup available at: {backup_dir}")
            print("   You can restore from backup if needed")
        
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)