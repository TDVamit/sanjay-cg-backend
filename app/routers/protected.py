from fastapi import APIRouter, Depends

from app.models.user import User
from app.core.security import get_current_user

router = APIRouter(prefix="/protected", tags=["Protected Routes"])


@router.get("/profile")
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get user profile information
    
    This is an example of a protected route that requires authentication
    """
    return {
        "message": f"Hello {current_user.username}!",
        "user_info": {
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "is_active": current_user.is_active,
            "member_since": current_user.created_at
        }
    }


@router.get("/dashboard")
async def get_dashboard(current_user: User = Depends(get_current_user)):
    """
    Get user dashboard data
    
    Another example of a protected route
    """
    return {
        "message": f"Welcome to your dashboard, {current_user.username}!",
        "stats": {
            "login_count": 1,  # This would come from your business logic
            "last_login": "2024-01-15T10:30:00",
            "account_status": "active"
        }
    }


@router.get("/settings")
async def get_user_settings(current_user: User = Depends(get_current_user)):
    """
    Get user settings
    
    Protected route for user settings
    """
    return {
        "user_id": current_user.id,
        "preferences": {
            "theme": "light",
            "notifications": True,
            "language": "en"
        }
    } 