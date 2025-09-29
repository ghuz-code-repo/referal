"""
Authentication middleware and decorators for Flask applications
"""

import jwt
import json
import base64
from functools import wraps
from typing import List, Optional, Dict, Any, Callable
from flask import request, g, jsonify, current_app
import logging

from .auth_client import AuthClient
from .exceptions import PermissionDeniedError, InvalidTokenError, ConfigurationError

logger = logging.getLogger(__name__)


class UserContext:
    """User context extracted from auth headers"""
    
    def __init__(self, user_id: str, username: str, full_name: str = None, 
                 roles: List[str] = None, permissions: List[str] = None, 
                 is_admin: bool = False, raw_headers: Dict[str, str] = None):
        self.user_id = user_id
        self.username = username
        self.full_name = full_name or username
        self.roles = roles or []
        self.permissions = permissions or []
        self.is_admin = is_admin
        self.raw_headers = raw_headers or {}
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        return permission in self.permissions
    
    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(perm in self.permissions for perm in permissions)
    
    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if user has all specified permissions"""
        return all(perm in self.permissions for perm in permissions)
    
    def has_role(self, role: str) -> bool:
        """Check if user has specific role"""
        return role in self.roles
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "full_name": self.full_name,
            "roles": self.roles,
            "permissions": self.permissions,
            "is_admin": self.is_admin
        }


class AuthMiddleware:
    """Authentication middleware for Flask applications"""
    
    def __init__(self, app=None, auth_client: AuthClient = None, 
                 jwt_secret: str = None, verify_signature: bool = True):
        self.auth_client = auth_client
        self.jwt_secret = jwt_secret
        self.verify_signature = verify_signature
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        app.before_request(self.before_request)
        
        # Store config
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['auth_middleware'] = self
    
    def before_request(self):
        """Extract user context from request headers"""
        try:
            user_context = self.extract_user_context(request.headers)
            g.user = user_context
            g.auth_client = self.auth_client
        except Exception as e:
            logger.error(f"Failed to extract user context: {e}")
            g.user = None
            g.auth_client = self.auth_client
    
    def extract_user_context(self, headers: Dict[str, str]) -> Optional[UserContext]:
        """Extract user context from headers"""
        
        # Method 1: JWT token in Authorization header
        auth_header = headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]
            return self._extract_from_jwt(token)
        
        # Method 2: Gateway-injected headers
        user_id = headers.get('X-User-Id')
        username = headers.get('X-User-Name')
        
        if user_id and username:
            return self._extract_from_gateway_headers(headers)
        
        # Method 3: Internal service token
        internal_token = headers.get('X-Internal-Auth')
        if internal_token:
            return self._extract_from_internal_token(internal_token)
        
        return None
    
    def _extract_from_jwt(self, token: str) -> UserContext:
        """Extract user context from JWT token"""
        try:
            if self.verify_signature and self.jwt_secret:
                payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            else:
                # For development/internal use - decode without verification
                payload = jwt.decode(token, options={"verify_signature": False})
            
            return UserContext(
                user_id=payload.get('user_id'),
                username=payload.get('username'),
                full_name=payload.get('full_name'),
                roles=payload.get('roles', []),
                permissions=payload.get('permissions', []),
                is_admin=payload.get('is_admin', False)
            )
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid JWT token: {e}")
    
    def _extract_from_gateway_headers(self, headers: Dict[str, str]) -> UserContext:
        """Extract user context from gateway-injected headers"""
        
        def decode_header_value(value: str) -> str:
            """Decode base64 encoded header value"""
            try:
                return base64.b64decode(value).decode('utf-8')
            except:
                return value
        
        user_id = headers.get('X-User-Id', '')
        username = headers.get('X-User-Name', '')
        full_name = decode_header_value(headers.get('X-User-Full-Name', ''))
        
        # Parse roles and permissions
        roles_str = headers.get('X-User-Service-Roles', '')
        permissions_str = headers.get('X-User-Service-Permissions', '')
        
        roles = [r.strip() for r in roles_str.split(',') if r.strip()] if roles_str else []
        permissions = [p.strip() for p in permissions_str.split(',') if p.strip()] if permissions_str else []
        
        is_admin = headers.get('X-User-Admin', 'false').lower() == 'true'
        
        return UserContext(
            user_id=user_id,
            username=username,
            full_name=full_name,
            roles=roles,
            permissions=permissions,
            is_admin=is_admin,
            raw_headers=dict(headers)
        )
    
    def _extract_from_internal_token(self, token: str) -> UserContext:
        """Extract user context from internal service token"""
        try:
            # Decode base64 token
            decoded = base64.b64decode(token).decode('utf-8')
            data = json.loads(decoded)
            
            return UserContext(
                user_id=data.get('user_id'),
                username=data.get('username'),
                full_name=data.get('full_name'),
                roles=data.get('roles', []),
                permissions=data.get('permissions', []),
                is_admin=data.get('is_admin', False)
            )
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
            raise InvalidTokenError(f"Invalid internal token: {e}")


def get_current_user() -> Optional[UserContext]:
    """Get current user from Flask g object"""
    return getattr(g, 'user', None)


def require_permission(permission: str, allow_admin: bool = True):
    """Decorator to require specific permission"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            
            if not user:
                return jsonify({
                    "error": "Authentication required",
                    "code": "AUTH_REQUIRED"
                }), 401
            
            # Admin bypass
            if allow_admin and user.is_admin:
                return f(*args, **kwargs)
            
            # Check permission
            if not user.has_permission(permission):
                return jsonify({
                    "error": f"Permission denied: {permission}",
                    "code": "PERMISSION_DENIED",
                    "required_permission": permission
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_any_permission(permissions: List[str], allow_admin: bool = True):
    """Decorator to require any of the specified permissions"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            
            if not user:
                return jsonify({
                    "error": "Authentication required", 
                    "code": "AUTH_REQUIRED"
                }), 401
            
            # Admin bypass
            if allow_admin and user.is_admin:
                return f(*args, **kwargs)
            
            # Check permissions
            if not user.has_any_permission(permissions):
                return jsonify({
                    "error": f"Permission denied. Required one of: {', '.join(permissions)}",
                    "code": "PERMISSION_DENIED",
                    "required_permissions": permissions
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_role(role: str, allow_admin: bool = True):
    """Decorator to require specific role (for backward compatibility)"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            
            if not user:
                return jsonify({
                    "error": "Authentication required",
                    "code": "AUTH_REQUIRED"
                }), 401
            
            # Admin bypass
            if allow_admin and user.is_admin:
                return f(*args, **kwargs)
            
            # Check role
            if not user.has_role(role):
                return jsonify({
                    "error": f"Role denied: {role}",
                    "code": "ROLE_DENIED", 
                    "required_role": role
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator