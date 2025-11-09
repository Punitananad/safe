"""
PostgreSQL Type Compatibility Fix for SQLAlchemy
Fixes the 'Unknown PG numeric type: 1043' error
"""

def apply_postgresql_fixes():
    """Apply PostgreSQL type compatibility fixes"""
    try:
        from sqlalchemy.dialects.postgresql import psycopg2
        from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime
        import sqlalchemy.exc as exc
        
        # Store original method
        original_result_processor = psycopg2.PGDialect_psycopg2.result_processor
        
        def patched_result_processor(self, type_, coltype):
            """Patched result processor that handles unknown PostgreSQL types"""
            # Handle common PostgreSQL type OIDs that cause issues
            type_mapping = {
                1043: String(),      # VARCHAR
                25: Text(),          # TEXT  
                23: Integer(),       # INTEGER
                701: Float(),        # FLOAT8
                16: Boolean(),       # BOOLEAN
                1114: DateTime(),    # TIMESTAMP
                1184: DateTime(),    # TIMESTAMPTZ
            }
            
            if coltype in type_mapping:
                mapped_type = type_mapping[coltype]
                return mapped_type.result_processor(self, coltype)
            
            # Fall back to original method for other types
            try:
                return original_result_processor(self, type_, coltype)
            except exc.InvalidRequestError as e:
                if "Unknown PG numeric type" in str(e):
                    # Default to String for unknown types
                    return String().result_processor(self, coltype)
                raise
        
        # Apply the patch
        psycopg2.PGDialect_psycopg2.result_processor = patched_result_processor
        print("PostgreSQL type compatibility fix applied successfully")
        return True
        
    except ImportError:
        print("psycopg2 not available, skipping PostgreSQL fixes")
        return False
    except Exception as e:
        print(f"Error applying PostgreSQL fixes: {e}")
        return False

def fix_sqlalchemy_postgresql():
    """Alternative fix using SQLAlchemy type registry"""
    try:
        from sqlalchemy.dialects.postgresql import base
        from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime
        
        # Register type handlers for common PostgreSQL types
        if hasattr(base, 'ischema_names'):
            base.ischema_names.update({
                'varchar': String,
                'text': Text,
                'integer': Integer,
                'float8': Float,
                'boolean': Boolean,
                'timestamp': DateTime,
                'timestamptz': DateTime,
            })
            
        return True
    except Exception as e:
        print(f"Error in SQLAlchemy PostgreSQL fix: {e}")
        return False

def apply_engine_level_fix():
    """Apply engine-level PostgreSQL type fixes"""
    try:
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        from sqlalchemy.dialects.postgresql import psycopg2
        
        @event.listens_for(Engine, "connect")
        def set_postgresql_compatibility(dbapi_connection, connection_record):
            """Set PostgreSQL compatibility options"""
            try:
                with dbapi_connection.cursor() as cursor:
                    # Set standard_conforming_strings to handle string literals properly
                    cursor.execute("SET standard_conforming_strings = on")
            except Exception:
                pass  # Ignore if setting fails
        
        print("Engine-level PostgreSQL fix applied")
        return True
    except Exception as e:
        print(f"Error applying engine-level fix: {e}")
        return False

# Apply fixes when module is imported
if __name__ == "__main__":
    apply_postgresql_fixes()
    fix_sqlalchemy_postgresql()
    apply_engine_level_fix()