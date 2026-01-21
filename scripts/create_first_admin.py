import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import db
from backend.models import UserRole
import uuid
import bcrypt

# Create a system admin user
admin_id = str(uuid.uuid4())
admin_email = "admin@system.com"
admin_password = "admin123"  # Change this!

# Hash password directly with bcrypt (workaround for passlib issue)
password_bytes = admin_password.encode('utf-8')
password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')

# Create admin user (no company_id for system admin)
user = db.create_user(
    user_id=admin_id,
    email=admin_email,
    password_hash=password_hash,
    company_id="SYSTEM",  # Special value for system admins (DynamoDB GSI doesn't allow empty strings)
    role=UserRole.ADMIN  # Use enum instead of string
)

print(f"Admin user created!")
print(f"Email: {admin_email}")
print(f"Password: {admin_password}")
print(f"User ID: {admin_id}")