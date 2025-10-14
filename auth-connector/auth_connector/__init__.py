"""
Auth Connector - Universal authentication and authorization module
for integrating services with the gateway auth-service.

Supports:
- Permission-based authorization
- User context extraction from headers
- Document requests from auth-service
- Permission validation and caching
- Service Discovery integration
- Easy integration with Flask, FastAPI, Django
"""

__version__ = "1.1.0"
__author__ = "Analytics Team"

from .auth_middleware import AuthMiddleware, require_permission, require_any_permission, get_current_user
from .auth_client import AuthClient
from .permissions import PermissionRegistry
from .exceptions import AuthError, PermissionDeniedError, InvalidTokenError
from .service_discovery import ServiceDiscoveryClient, init_service_discovery_flask, init_service_discovery_fastapi

__all__ = [
    "AuthMiddleware",
    "AuthClient", 
    "PermissionRegistry",
    "require_permission",
    "require_any_permission",
    "get_current_user",
    "AuthError",
    "PermissionDeniedError", 
    "InvalidTokenError",
    "ServiceDiscoveryClient",
    "init_service_discovery_flask",
    "init_service_discovery_fastapi"
]