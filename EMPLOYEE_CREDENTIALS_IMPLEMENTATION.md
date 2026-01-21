# Employee Credentials Implementation

## Overview

When a company is created, the system now automatically creates an employee user account that can be used to log in to the Company Panel and access the agent.

## Backend Implementation

### 1. Company Creation (`backend/routes/admin.py`)

- **Automatic Employee User Creation**: When a company is created, an employee user is automatically created
- **Default Credentials**:
  - Email: `employee@{company_name}.com` (sanitized company name)
  - Password: `password123` (if not provided)
- **Custom Credentials**: Admin can optionally provide custom employee email and password
- **Response**: Returns both admin and employee credentials in the response

### 2. API Changes

**Endpoint**: `POST /admin/companies`

**Request Body** (all fields optional except name, admin_email, admin_password):
```json
{
  "name": "Acme Corp",
  "admin_email": "admin@acme.com",
  "admin_password": "admin123456",
  "employee_email": "support@acme.com",  // Optional
  "employee_password": "support123456"   // Optional
}
```

**Response**:
```json
{
  "company_id": "...",
  "name": "Acme Corp",
  "status": "active",
  "employee_credentials": {
    "email": "employee@acmecorp.com",
    "password": "password123",
    "role": "employee"
  },
  "admin_credentials": {
    "email": "admin@acme.com",
    "role": "admin"
  }
}
```

## Frontend Implementation

### 1. Admin Panel (`frontend/admin-panel/app/companies/page.tsx`)

**Company Creation Form**:
- Added optional employee email and password fields
- Shows helpful placeholder text
- Auto-generates credentials if fields are left empty

**Credentials Modal**:
- Automatically displays after company creation
- Shows both employee and admin credentials
- Clear visual distinction between employee (blue) and admin (green) credentials
- One-time display (credentials won't be shown again)

### 2. Company Panel (`frontend/company-panel`)

**No Changes Required**:
- The Company Panel login already works with employee credentials
- Uses the same `/auth/login` endpoint
- Employee users can log in and access the chat interface

## Usage Flow

### 1. Create Company (Admin Panel)

1. Navigate to Admin Panel → Companies
2. Click "Create Company"
3. Fill in:
   - Company Name (required)
   - Admin Email (required)
   - Admin Password (required)
   - Employee Email (optional - auto-generated if empty)
   - Employee Password (optional - defaults to "password123")
4. Click "Create"
5. **Credentials Modal appears** showing:
   - Employee email and password
   - Admin email
6. Save these credentials (they won't be shown again)
7. Deployment starts automatically

### 2. Login as Employee (Company Panel)

1. Navigate to Company Panel login page
2. Enter employee credentials:
   - Email: `employee@{company_name}.com` (or custom)
   - Password: `password123` (or custom)
3. Click "Login"
4. Access the chat interface to interact with the agent

### 3. Login as Admin (Admin Panel)

1. Navigate to Admin Panel login page
2. Enter admin credentials:
   - Email: (provided during company creation)
   - Password: (provided during company creation)
3. Click "Login"
4. Access admin features (company management, knowledge base, etc.)

## Security Notes

1. **Default Password**: The default employee password is `password123`. Users should change this after first login (if password change functionality is implemented).

2. **Credentials Display**: Credentials are only shown once after company creation. They are not stored in the response after that.

3. **Role-Based Access**:
   - **Employee**: Can access Company Panel, chat with agent
   - **Admin**: Can access Admin Panel, manage company, upload knowledge base

## Testing

### Test Employee Login

```bash
# 1. Create company via Admin Panel or API
curl -X POST http://localhost:8000/admin/companies \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Company",
    "admin_email": "admin@test.com",
    "admin_password": "admin123456"
  }'

# Response includes employee_credentials
# {
#   "employee_credentials": {
#     "email": "employee@testcompany.com",
#     "password": "password123"
#   }
# }

# 2. Login as employee
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "employee@testcompany.com",
    "password": "password123"
  }'

# 3. Use token to chat with agent
curl -X POST http://localhost:8000/company/chat \
  -H "Authorization: Bearer EMPLOYEE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are your business hours?",
    "session_id": "test-session-1234567890123456789012345"
  }'
```

## Frontend Files Modified

1. **Backend**:
   - `backend/models.py` - Added optional employee fields to `CompanyCreate`
   - `backend/routes/admin.py` - Employee user creation logic

2. **Admin Panel**:
   - `frontend/admin-panel/lib/api.ts` - Updated Company interface and create method
   - `frontend/admin-panel/app/companies/page.tsx` - Added employee fields and credentials modal

3. **Company Panel**:
   - No changes needed (already compatible)

## Future Enhancements

1. **Password Change**: Allow employees to change their password after first login
2. **Multiple Employees**: Allow admins to create additional employee accounts
3. **Password Reset**: Implement password reset functionality
4. **Email Notifications**: Send credentials via email instead of showing in modal
5. **Credential Export**: Allow downloading credentials as PDF or text file
