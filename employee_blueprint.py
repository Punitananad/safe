from flask import Blueprint

# Create a minimal employee blueprint to satisfy the import
employee_bp = Blueprint('employee', __name__)

def init_employee_db(db):
    """Initialize employee database - placeholder function"""
    pass

# Add a simple route to avoid empty blueprint
@employee_bp.route('/')
def employee_index():
    return "Employee Blueprint Loaded"