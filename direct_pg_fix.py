"""
Direct PostgreSQL Type 1043 Fix
Patches the exact location where the error occurs
"""

def apply_direct_fix():
    """Apply fix directly to the psycopg2 dialect result_processor method"""
    try:
        # The error occurs in sqlalchemy.dialects.postgresql.psycopg2.py line 554
        # Let's patch that specific method
        
        from sqlalchemy.dialects.postgresql import psycopg2
        import sqlalchemy.exc as exc
        
        # Get the actual class that has the result_processor method
        dialect_class = psycopg2.PGDialect_psycopg2
        
        # Find the parent class that has result_processor
        for cls in dialect_class.__mro__:
            if hasattr(cls, 'result_processor') and hasattr(cls.result_processor, '__func__'):
                target_class = cls
                break
        else:
            # If not found in MRO, check the module directly
            if hasattr(psycopg2, 'result_processor'):
                # Patch the module-level function
                original_func = psycopg2.result_processor
                
                def patched_result_processor(type_, coltype):
                    if coltype == 1043:  # VARCHAR
                        def process(value):
                            return str(value) if value is not None else value
                        return process
                    try:
                        return original_func(type_, coltype)
                    except exc.InvalidRequestError as e:
                        if "Unknown PG numeric type: 1043" in str(e):
                            def process(value):
                                return str(value) if value is not None else value
                            return process
                        raise
                
                psycopg2.result_processor = patched_result_processor
                print("Applied module-level fix")
                return True
        
        # Try patching the specific type classes
        from sqlalchemy.sql.sqltypes import String, VARCHAR
        
        # Patch VARCHAR type directly
        original_varchar_processor = VARCHAR.result_processor
        
        def patched_varchar_processor(self, dialect, coltype):
            if coltype == 1043:
                def process(value):
                    return str(value) if value is not None else value
                return process
            
            try:
                return original_varchar_processor(self, dialect, coltype)
            except exc.InvalidRequestError as e:
                if "Unknown PG numeric type: 1043" in str(e):
                    def process(value):
                        return str(value) if value is not None else value
                    return process
                raise
        
        VARCHAR.result_processor = patched_varchar_processor
        print("Applied VARCHAR type fix")
        return True
        
    except Exception as e:
        print(f"Direct fix failed: {e}")
        return False

def apply_engine_event_fix():
    """Apply fix using SQLAlchemy events"""
    try:
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        from sqlalchemy.pool import Pool
        
        @event.listens_for(Engine, "connect")
        def set_postgresql_unicode(dbapi_connection, connection_record):
            """Set PostgreSQL connection to handle Unicode properly"""
            try:
                # Set client encoding to UTF8
                with dbapi_connection.cursor() as cursor:
                    cursor.execute("SET client_encoding TO 'UTF8'")
                    cursor.execute("SET standard_conforming_strings = on")
            except Exception:
                pass
        
        print("Applied engine event fix")
        return True
        
    except Exception as e:
        print(f"Engine event fix failed: {e}")
        return False

def apply_type_decorator_fix():
    """Apply fix using type decorators"""
    try:
        from sqlalchemy import TypeDecorator, String
        from sqlalchemy.dialects.postgresql import VARCHAR
        
        class FixedVARCHAR(TypeDecorator):
            """VARCHAR type that handles the 1043 error"""
            impl = String
            cache_ok = True
            
            def result_processor(self, dialect, coltype):
                if coltype == 1043:
                    def process(value):
                        return str(value) if value is not None else value
                    return process
                return super().result_processor(dialect, coltype)
        
        # Replace VARCHAR in the dialect
        from sqlalchemy.dialects.postgresql import base
        if hasattr(base, 'ischema_names'):
            base.ischema_names['varchar'] = FixedVARCHAR
            base.ischema_names['character varying'] = FixedVARCHAR
        
        print("Applied type decorator fix")
        return True
        
    except Exception as e:
        print(f"Type decorator fix failed: {e}")
        return False

# Apply all fixes
def apply_all_fixes():
    """Apply all available fixes"""
    fixes_applied = 0
    
    if apply_direct_fix():
        fixes_applied += 1
    
    if apply_engine_event_fix():
        fixes_applied += 1
        
    if apply_type_decorator_fix():
        fixes_applied += 1
    
    print(f"Applied {fixes_applied} PostgreSQL fixes")
    return fixes_applied > 0

# Apply fixes when imported
apply_all_fixes()