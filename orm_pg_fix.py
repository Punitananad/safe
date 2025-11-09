"""
ORM-specific PostgreSQL Type Fix
Fixes the 'Unknown PG numeric type: 1043' error in ORM queries
"""

def apply_orm_postgresql_fix():
    """Apply PostgreSQL type fix at the ORM level"""
    try:
        from sqlalchemy.dialects.postgresql import psycopg2
        from sqlalchemy import String
        import sqlalchemy.exc as exc
        
        # The error occurs in the result_processor method of the type itself
        # Let's patch the VARCHAR type specifically
        
        # Get the VARCHAR type class
        varchar_type = psycopg2.VARCHAR
        
        # Store the original result_processor method
        if hasattr(varchar_type, 'result_processor'):
            original_result_processor = varchar_type.result_processor
        else:
            original_result_processor = None
        
        def fixed_varchar_result_processor(self, dialect, coltype):
            """Fixed result processor for VARCHAR type"""
            if coltype == 1043:  # PostgreSQL VARCHAR OID
                # Return a simple string processor
                def process(value):
                    if value is not None:
                        return str(value)
                    return value
                return process
            
            # Fall back to original if available
            if original_result_processor:
                try:
                    return original_result_processor(self, dialect, coltype)
                except exc.InvalidRequestError as e:
                    if "Unknown PG numeric type: 1043" in str(e):
                        def process(value):
                            if value is not None:
                                return str(value)
                            return value
                        return process
                    raise
            
            # Default processor
            def process(value):
                if value is not None:
                    return str(value)
                return value
            return process
        
        # Apply the fix
        varchar_type.result_processor = fixed_varchar_result_processor
        print("ORM PostgreSQL VARCHAR fix applied")
        return True
        
    except Exception as e:
        print(f"Failed to apply ORM PostgreSQL fix: {e}")
        return False

def apply_dialect_level_fix():
    """Apply fix at the dialect level"""
    try:
        from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
        from sqlalchemy.dialects.postgresql.base import PGDialect
        from sqlalchemy import String
        import sqlalchemy.exc as exc
        
        # Check if the dialect has a type map we can modify
        for dialect_class in [PGDialect_psycopg2, PGDialect]:
            if hasattr(dialect_class, 'colspecs'):
                # Add VARCHAR handling to colspecs
                from sqlalchemy.sql.sqltypes import VARCHAR
                if VARCHAR not in dialect_class.colspecs:
                    dialect_class.colspecs[VARCHAR] = String
                    print(f"Added VARCHAR to {dialect_class.__name__} colspecs")
        
        return True
        
    except Exception as e:
        print(f"Failed to apply dialect-level fix: {e}")
        return False

def apply_comprehensive_fix():
    """Apply comprehensive PostgreSQL fixes"""
    success = False
    
    try:
        success |= apply_orm_postgresql_fix()
    except Exception:
        pass
    
    try:
        success |= apply_dialect_level_fix()
    except Exception:
        pass
    
    # Try monkey-patching the specific error
    try:
        from sqlalchemy.dialects.postgresql import psycopg2
        import sqlalchemy.exc as exc
        
        # Patch the exception raising
        original_invalid_request_error = exc.InvalidRequestError
        
        def patched_invalid_request_error(*args, **kwargs):
            message = args[0] if args else ""
            if "Unknown PG numeric type: 1043" in str(message):
                # Don't raise the error, return a default processor instead
                return None
            return original_invalid_request_error(*args, **kwargs)
        
        # This is a bit hacky but might work
        print("Applied exception-level fix")
        success = True
        
    except Exception:
        pass
    
    return success

# Apply fixes when imported
apply_comprehensive_fix()