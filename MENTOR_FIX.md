# Mentor Model Fix Instructions

## Issue
The mentor model is not working when trying to create mentors from the admin panel. This happens because the mentor table may not exist or is missing required columns.

## Quick Fix Options

### Option 1: Use Admin Dashboard (Recommended)
1. Go to the admin dashboard
2. Scroll down to "Quick Actions" section
3. Click the "Initialize Database" button
4. This will create the mentor table and add missing columns

### Option 2: Run Python Script
```bash
python run_init.py
```

### Option 3: Manual Database Initialization
```bash
python init_database.py
```

## What the Fix Does
1. Creates the `mentor` table if it doesn't exist
2. Adds the `commission_pct` column if missing
3. Ensures all required database tables are properly initialized

## After Running the Fix
- Try creating a mentor again from the admin panel
- The "mentor model not available" error should be resolved
- All mentor functionality should work properly

## Technical Details
The issue occurs because:
1. The mentor table might not exist in the database
2. The `commission_pct` column might be missing
3. The mentor model initialization might have failed during app startup

The fix ensures all database tables are created and properly configured.