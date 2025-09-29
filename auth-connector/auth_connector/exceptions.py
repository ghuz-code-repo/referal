"""
Custom exceptions for auth-connector module
"""

class AuthError(Exception):
    """Base authentication error"""
    pass

class PermissionDeniedError(AuthError):
    """Raised when user lacks required permission"""
    def __init__(self, permission, user_id=None):
        self.permission = permission
        self.user_id = user_id
        super().__init__(f"Permission denied: {permission} for user {user_id}")

class InvalidTokenError(AuthError):
    """Raised when auth token is invalid or expired"""
    pass

class AuthServiceUnavailableError(AuthError):
    """Raised when auth-service is not reachable"""
    pass

class ConfigurationError(AuthError):
    """Raised when auth-connector is misconfigured"""
    pass