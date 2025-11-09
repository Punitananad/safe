# Symbol Fetching from dhan_symbols.db

This guide explains how to fetch symbols from your `dhan_symbols.db` file.

## Database Structure

Your `dhan_symbols.db` contains an `instruments` table with the following columns:
- `SYMBOL_NAME`: The actual symbol name (e.g., "STATE BANK OF INDIA")
- `DISPLAY_NAME`: Display name for the symbol
- `SECURITY_ID`: Unique identifier for the symbol
- `EXCH_ID`: Exchange ID (NSE, BSE, etc.)
- `SEGMENT`: Market segment (E for equity)

## Files Created

1. **`symbol_utils.py`** - Main utility functions for symbol operations
2. **`integration_example.py`** - Example Flask app showing integration
3. **`test_symbol_search.py`** - Test script for symbol search
4. **`check_available_symbols.py`** - Script to explore database contents

## Key Functions

### `search_symbols(query, limit=10)`
Search for symbols matching a query string.

```python
from symbol_utils import search_symbols

# Search for bank-related symbols
results = search_symbols("BANK", 5)
for result in results:
    print(f"{result['symbol']} - {result['name']} (ID: {result['security_id']})")
```

### `resolve_symbol(symbol_name)`
Get detailed information for a specific symbol.

```python
from symbol_utils import resolve_symbol

# Resolve State Bank of India
symbol_data = resolve_symbol("STATE BANK OF INDIA")
if symbol_data:
    print(f"Security ID: {symbol_data['security_id']}")
    print(f"Exchange: {symbol_data['exchange']}")
```

### `get_symbol_by_id(security_id)`
Get symbol information by security ID.

```python
from symbol_utils import get_symbol_by_id

# Get symbol by ID
symbol_data = get_symbol_by_id(3045)
if symbol_data:
    print(f"Symbol: {symbol_data['symbol']}")
```

## Integration with Your Flask App

Your `app.py` has been updated to use SQLite instead of PostgreSQL for symbol fetching:

1. **`fetch_all_symbols()`** - Now reads from SQLite database
2. **`search_equity_symbols()`** - Updated to use SQLite queries
3. **`resolve_input()`** - Modified to work with SQLite

## Example Symbols in Your Database

- **State Bank of India**: `STATE BANK OF INDIA` (ID: 3045)
- **Axis Bank**: `AXIS BANK LIMITED` (ID: 5900)
- **HDFC Bank**: `HDFC BANK LTD` (ID: not shown in sample)
- **Bank of Baroda**: `BANK OF BARODA` (ID: 4668)

## Testing

Run the test scripts to verify functionality:

```bash
# Test symbol utilities
python symbol_utils.py

# Check available symbols
python check_available_symbols.py

# Find specific symbols
python find_sbi_symbol.py

# Test integration
python integration_example.py
```

## API Endpoints (if using integration_example.py)

- `GET /api/symbols/search?q=BANK` - Search for symbols
- `GET /api/symbols/resolve/STATE BANK OF INDIA` - Resolve specific symbol
- `GET /api/symbols/by-id/3045` - Get symbol by security ID

## Important Notes

1. **Symbol Names**: Many symbols use full company names (e.g., "STATE BANK OF INDIA" not "SBIN")
2. **Case Sensitivity**: All searches are case-insensitive
3. **NSE Equity Only**: Filters are applied to show only NSE equity symbols (EXCH_ID='NSE', SEGMENT='E')
4. **Scoring System**: Search results are ranked by relevance (exact match > starts with > contains)

## Next Steps

1. Test the updated `app.py` with your existing Flask application
2. Verify that symbol search works in your web interface
3. Check that price fetching works with the resolved security IDs
4. Consider adding caching for frequently searched symbols

## Troubleshooting

If you encounter issues:

1. **Database not found**: Ensure `instance/dhan_symbols.db` exists
2. **No results**: Check if the symbol exists using `check_available_symbols.py`
3. **Connection errors**: Verify SQLite3 is available in your Python environment

The symbol fetching functionality is now ready to use with your existing CalculatenTrade application!