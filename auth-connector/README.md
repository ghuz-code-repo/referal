# Auth Connector

Universal authentication and authorization connector for microservices integration with gateway auth-service.

## Features

- 🔐 **Permission-based authorization** - Fine-grained access control
- 🏷️ **Multiple auth methods** - JWT tokens, gateway headers, internal tokens
- 🔄 **Permission sync** - Auto-sync service permissions with auth-service  
- 🚀 **Framework agnostic** - Works with Flask, FastAPI, Django
- 📦 **Easy integration** - Drop-in middleware and decorators
- 🎯 **Caching** - Built-in permission caching for performance

## Quick Start

### Installation

```bash
# Basic installation
pip install -e .

# With Flask support
pip install -e ".[flask]"

# With FastAPI support  
pip install -e ".[fastapi]"
```

### Flask Integration

```python
from flask import Flask
from auth_connector import AuthMiddleware, AuthClient, require_permission, get_current_user

app = Flask(__name__)

# Setup auth client
auth_client = AuthClient(
    auth_service_url="http://gateway:8080",
    service_key="referal"
)

# Setup middleware
auth_middleware = AuthMiddleware(app, auth_client)

@app.route('/protected')
@require_permission('referal.users.view')
def protected_route():
    user = get_current_user()
    return f"Hello {user.full_name}!"

@app.route('/admin-only')  
@require_permission('referal.admin.manage_users')
def admin_route():
    return "Admin only content"
```

### Permission Registry

```python
from auth_connector import PermissionRegistry, CommonPermissions

# Create registry
registry = PermissionRegistry("referal")

# Register permissions
registry.register(
    name="referal.users.view",
    display_name="View Users", 
    description="Permission to view referral users",
    category="users"
)

# Use common patterns
for name, display, desc in CommonPermissions.crud_permissions("payments"):
    registry.register(name, display, desc, "payments")

# Export for sync
permissions_dict = registry.to_dict()
```

### User Context

```python
from auth_connector import get_current_user

def some_function():
    user = get_current_user()
    
    if user.has_permission('referal.reports.view'):
        return generate_report()
    
    if user.is_admin:
        return admin_data()
        
    return user_data()
```

## API Reference

### AuthMiddleware

Main middleware class for extracting user context from requests.

```python
middleware = AuthMiddleware(
    app=flask_app,                    # Flask app instance
    auth_client=auth_client,          # AuthClient instance  
    jwt_secret="secret",              # JWT secret for verification
    verify_signature=True             # Whether to verify JWT signatures
)
```

### AuthClient

Client for communicating with auth-service.

```python
client = AuthClient(
    auth_service_url="http://auth:8080",  # Auth service URL
    service_key="my-service",             # Your service key
    timeout=10                            # Request timeout
)

# Get user permissions
permissions = client.get_user_permissions("user123")

# Get user documents
docs = client.get_user_document("user123", "passport")

# Sync permissions
client.sync_permissions(permissions_list)
```

### Decorators

#### @require_permission(permission, allow_admin=True)

Require specific permission for route access.

```python
@require_permission('service.action.resource')
def protected_function():
    pass
```

#### @require_any_permission(permissions, allow_admin=True)

Require any of the specified permissions.

```python
@require_any_permission(['read', 'write', 'admin'])
def flexible_access():
    pass
```

#### @require_role(role, allow_admin=True)

Require specific role (backward compatibility).

```python
@require_role('manager')
def manager_only():
    pass
```

## Authentication Methods

The connector supports multiple authentication methods:

### 1. Gateway Headers (Recommended)

Used when service is behind auth gateway:

```
X-User-Id: user123
X-User-Name: john.doe  
X-User-Full-Name: base64(John Doe)
X-User-Service-Roles: admin,manager
X-User-Service-Permissions: view,create,edit
X-User-Admin: true
```

### 2. JWT Tokens

Standard JWT tokens with user claims:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### 3. Internal Service Tokens

For service-to-service communication:

```
X-Internal-Auth: base64({"user_id": "123", "permissions": [...]})
```

## Error Handling

```python
from auth_connector.exceptions import PermissionDeniedError, AuthServiceUnavailableError

try:
    permissions = auth_client.get_user_permissions("user123")
except AuthServiceUnavailableError:
    # Handle auth service downtime
    permissions = []  # Fallback or cached permissions
```

## Configuration

### Environment Variables

```bash
AUTH_SERVICE_URL=http://gateway:8080
SERVICE_KEY=my-service
JWT_SECRET=your-secret-key
AUTH_CACHE_TTL=300
```

### Flask Config

```python
app.config.update({
    'AUTH_SERVICE_URL': 'http://gateway:8080',
    'AUTH_SERVICE_KEY': 'my-service', 
    'AUTH_JWT_SECRET': 'secret',
    'AUTH_VERIFY_SIGNATURE': True
})
```

## Permission Patterns

### Resource-based permissions

```
service.resource.action
referal.users.view
referal.payments.create  
referal.reports.export
```

### Role-based permissions

```
service.role.capability
referal.admin.manage_users
referal.manager.approve_payments
```

### Feature-based permissions

```
service.feature.access
referal.dashboard.view
referal.analytics.access
```

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

### Integration with Service

1. Install auth-connector in your service
2. Create permission registry with your permissions
3. Add endpoint for permission sync
4. Initialize auth middleware
5. Decorate routes with permission requirements
6. Test with auth gateway

## License

MIT License - see LICENSE file for details.