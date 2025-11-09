"""
Direct PostgreSQL Type 1043 (VARCHAR) Fix for SQLAlchemy
This fixes the specific 'Unknown PG numeric type: 1043' error
"""

def fix_postgresql_type_1043():
    """Fix the specific PostgreSQL type 1043 (VARCHAR) error"""
    try:
        from sqlalchemy.dialects.postgresql import psycopg2
        from sqlalchemy import String
        import sqlalchemy.exc as exc
        
        # Get the original result_processor method
        original_method = psycopg2.PGDialect_psycopg2.result_processor
        
        def fixed_result_processor(self, type_, coltype):
            """Fixed result processor that handles type 1043 (VARCHAR)"""
            if coltype == 1043:  # VARCHAR type
                return String().result_processor(self, coltype)
            
            try:
                return original_method(self, type_, coltype)
            except exc.InvalidRequestError as e:
                if "Unknown PG numeric type: 1043" in str(e):
                    return String().result_processor(self, coltype)
                raise
        
        # Apply the fix
        psycopg2.PGDialect_psycopg2.result_processor = fixed_result_processor
        print("PostgreSQL type 1043 (VARCHAR) fix applied successfully")
        return True
        
    except Exception as e:
        print(f"Failed to apply PostgreSQL type fix: {e}")
        return False

def apply_comprehensive_pg_fix():
    """Apply comprehensive PostgreSQL type fixes"""
    try:
        from sqlalchemy.dialects.postgresql import psycopg2
        from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime
        import sqlalchemy.exc as exc
        
        # Store original method
        original_method = psycopg2.PGDialect_psycopg2.result_processor
        
        def comprehensive_result_processor(self, type_, coltype):
            """Comprehensive result processor for PostgreSQL types"""
            # Map of PostgreSQL OID to SQLAlchemy types
            pg_type_map = {
                1043: String(),      # VARCHAR
                25: Text(),          # TEXT
                23: Integer(),       # INTEGER
                20: Integer(),       # BIGINT
                21: Integer(),       # SMALLINT
                701: Float(),        # FLOAT8
                700: Float(),        # FLOAT4
                1700: Float(),       # NUMERIC
                16: Boolean(),       # BOOLEAN
                1114: DateTime(),    # TIMESTAMP
                1184: DateTime(),    # TIMESTAMPTZ
            }
            
            if coltype in pg_type_map:
                mapped_type = pg_type_map[coltype]
                return mapped_type.result_processor(self, coltype)
            
            try:
                return original_method(self, type_, coltype)
            except exc.InvalidRequestError as e:
                if "Unknown PG numeric type" in str(e):
                    # Default to String for any unknown type
                    return String().result_processor(self, coltype)
                raise
        
        # Apply the comprehensive fix
        psycopg2.PGDialect_psycopg2.result_processor = comprehensive_result_processor
        print("Comprehensive PostgreSQL type fix applied successfully")
        return True
        
    except Exception as e:
        print(f"Failed to apply comprehensive PostgreSQL fix: {e}")
        return False

# Apply the fix when imported
try:
    apply_comprehensive_pg_fix()
except Exception:
    try:
        fix_postgresql_type_1043()
    except Exception:
        pass