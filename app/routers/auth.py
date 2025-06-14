from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timedelta

from app.models.user import UserCreate, UserLogin, User, Token, RefreshTokenRequest
from app.database.mongodb import get_database
from app.core.security import (
    get_password_hash,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    store_refresh_token,
    validate_refresh_token,
    revoke_refresh_token,
    get_current_user,
    get_user,
)
from app.core.config import settings
from app.core.utils import generate_uuid, is_valid_uuid

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate):
    """
    Create a new user account
    
    - **username**: Unique username (3-50 characters)
    - **email**: Valid email address
    - **password**: Password (minimum 6 characters)
    - **full_name**: Optional full name
    """
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Check if user already exists
        existing_user = await db.users.find_one({
            "$or": [
                {"username": user_data.username},
                {"email": user_data.email}
            ]
        })
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered"
            )
        
        # Create new user with UUID4 as ID
        user_id = generate_uuid()
        hashed_password = get_password_hash(user_data.password)
        user_dict = {
            "_id": user_id,  # Use UUID4 string as ID
            "username": user_data.username,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "hashed_password": hashed_password,
            "is_active": True,
            "created_at": datetime.utcnow()
        }
        
        # Insert user into database
        result = await db.users.insert_one(user_dict)
        
        # Remove hashed_password from response
        user_dict.pop("hashed_password", None)
        
        return User(**user_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in register_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.post("/login", response_model=Token)
async def login_user(user_credentials: UserLogin):
    """
    Authenticate user and return access and refresh tokens
    
    - **username**: Username
    - **password**: Password
    
    Returns both access token (30 minutes) and refresh token (2 days).
    """
    try:
        user = await authenticate_user(user_credentials.username, user_credentials.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token (short-lived)
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        # Create refresh token (long-lived)
        refresh_token_expires = timedelta(days=2)
        refresh_token = create_refresh_token(
            data={"sub": user.username}, expires_delta=refresh_token_expires
        )
        
        # Store refresh token in database for security
        await store_refresh_token(user.username, refresh_token)
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60  # Convert to seconds
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in login_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


@router.post("/refresh", response_model=Token)
async def refresh_access_token(refresh_request: RefreshTokenRequest):
    """
    Refresh access token using refresh token
    
    - **refresh_token**: Valid refresh token received from login
    
    Returns a new access token and refresh token pair.
    The old refresh token is automatically revoked.
    """
    try:
        # Validate the refresh token
        username = await validate_refresh_token(refresh_request.refresh_token)
        
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify user still exists and is active
        user = await get_user(username)
        if not user or not user.is_active:
            # Revoke the refresh token if user is inactive
            await revoke_refresh_token(username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
            )
        
        # Create new access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        # Create new refresh token (rotate refresh tokens for security)
        refresh_token_expires = timedelta(days=2)
        new_refresh_token = create_refresh_token(
            data={"sub": user.username}, expires_delta=refresh_token_expires
        )
        
        # Store new refresh token and revoke old one
        await store_refresh_token(user.username, new_refresh_token)
        
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in refresh_access_token: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token refresh service unavailable"
        )


@router.post("/logout")
async def logout_user(current_user: User = Depends(get_current_user)):
    """
    Logout user and revoke refresh token
    
    **Authentication required**: Include JWT token in Authorization header
    
    This will revoke the user's refresh token, effectively logging them out
    from all devices until they login again.
    """
    try:
        # Revoke the user's refresh token
        await revoke_refresh_token(current_user.username)
        
        return {
            "message": "Successfully logged out",
            "username": current_user.username
        }
        
    except Exception as e:
        print(f"Error in logout_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Logout service unavailable"
        )


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information
    
    Requires valid JWT token in Authorization header
    """
    return current_user


@router.get("/user/{user_id}", response_model=User)
async def get_user_by_id(user_id: str):
    """
    Get user by ID
    
    - **user_id**: UUID string of the user
    """
    if not is_valid_uuid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format. Must be a valid UUID."
        )
    
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        user_data = await db.users.find_one({"_id": user_id})
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Remove sensitive data
        user_data.pop("hashed_password", None)
        
        return User(**user_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in get_user_by_id: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        ) 