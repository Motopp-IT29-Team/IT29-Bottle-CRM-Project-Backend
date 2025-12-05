"""
Activity Logger Utility

Provides a simple function to log user activities in the CRM system.
Usage:
    from common.activity_logger import log_activity
    log_activity(request, "CREATE", "Lead", entity_id=lead.id, entity_name=lead.title)
"""

from common.models import ActivityLog


def log_activity(
    request,
    action: str,
    entity_type: str,
    entity_id=None,
    entity_name: str = "",
    details: dict = None
):
    """
    Log a user activity in the system.
    
    Args:
        request: The HTTP request object (must have profile attached)
        action: The action performed (LOGIN, LOGOUT, CREATE, UPDATE, DELETE, VIEW)
        entity_type: The type of entity affected (Lead, Contact, Account, etc.)
        entity_id: The UUID of the entity (optional)
        entity_name: A display name for the entity (optional)
        details: Additional context as a dictionary (optional)
    
    Returns:
        ActivityLog instance or None if logging fails
    """
    try:
        # Get user info from request
        user = getattr(request, 'user', None)
        profile = getattr(request, 'profile', None)
        
        if not profile or not profile.org:
            return None
        
        # Create the log entry
        log_entry = ActivityLog.objects.create(
            user=user if user and user.is_authenticated else None,
            user_email=user.email if user and hasattr(user, 'email') else "",
            user_role=profile.role if profile else "",
            org=profile.org,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name or "",
            details=details or {},
        )
        
        return log_entry
    
    except Exception as e:
        # Don't let logging errors break the main flow
        print(f"Activity logging error: {e}")
        return None


def log_login(request):
    """Log a user login event."""
    return log_activity(
        request,
        action="LOGIN",
        entity_type="System",
        entity_name="User Login",
    )


def log_logout(request):
    """Log a user logout event."""
    return log_activity(
        request,
        action="LOGOUT",
        entity_type="System",
        entity_name="User Logout",
    )
