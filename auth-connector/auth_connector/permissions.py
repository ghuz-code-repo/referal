"""
Permission registry for service-specific permissions.
Allows services to declare their available permissions and sync them with auth-service.
"""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from .exceptions import ConfigurationError


@dataclass
class Permission:
    """Represents a single permission"""
    name: str
    display_name: str
    description: str
    category: Optional[str] = None


class PermissionRegistry:
    """Registry for service permissions that can sync with auth-service"""
    
    def __init__(self, service_key: str):
        self.service_key = service_key
        self._permissions: Dict[str, Permission] = {}
        self._categories: Dict[str, List[str]] = {}
    
    def register(self, name: str, display_name: str, description: str, category: str = None) -> Permission:
        """Register a new permission"""
        if not name:
            raise ConfigurationError("Permission name cannot be empty")
        
        permission = Permission(
            name=name,
            display_name=display_name,
            description=description,
            category=category
        )
        
        self._permissions[name] = permission
        
        if category:
            if category not in self._categories:
                self._categories[category] = []
            if name not in self._categories[category]:
                self._categories[category].append(name)
        
        return permission
    
    def get_permission(self, name: str) -> Optional[Permission]:
        """Get permission by name"""
        return self._permissions.get(name)
    
    def get_all_permissions(self) -> List[Permission]:
        """Get all registered permissions"""
        return list(self._permissions.values())
    
    def get_permissions_by_category(self, category: str) -> List[Permission]:
        """Get permissions by category"""
        if category not in self._categories:
            return []
        return [self._permissions[name] for name in self._categories[category]]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API serialization"""
        return {
            "service_key": self.service_key,
            "permissions": [
                {
                    "name": p.name,
                    "displayName": p.display_name,
                    "description": p.description,
                    "category": p.category
                }
                for p in self._permissions.values()
            ],
            "categories": list(self._categories.keys())
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# Common permission patterns for reuse
class CommonPermissions:
    """Common permission patterns that services can use"""
    
    @staticmethod
    def crud_permissions(resource: str) -> List[tuple]:
        """Generate standard CRUD permissions for a resource"""
        return [
            (f"{resource}.view", f"View {resource}", f"Permission to view {resource} data"),
            (f"{resource}.create", f"Create {resource}", f"Permission to create new {resource}"),
            (f"{resource}.edit", f"Edit {resource}", f"Permission to edit existing {resource}"),
            (f"{resource}.delete", f"Delete {resource}", f"Permission to delete {resource}"),
        ]
    
    @staticmethod
    def admin_permissions(service: str) -> List[tuple]:
        """Generate standard admin permissions for a service"""
        return [
            (f"{service}.admin.manage_users", "Manage Users", "Permission to manage service users"),
            (f"{service}.admin.view_logs", "View Logs", "Permission to view service logs"),
            (f"{service}.admin.export_data", "Export Data", "Permission to export service data"),
            (f"{service}.admin.manage_settings", "Manage Settings", "Permission to manage service settings"),
        ]