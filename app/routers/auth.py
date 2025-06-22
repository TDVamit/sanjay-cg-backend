from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from datetime import datetime, timedelta
import base64
import io
from PIL import Image

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


def compress_and_convert_to_webp(image_bytes: bytes, quality: int = 80, max_size: tuple = (800, 800)) -> str:
    """
    Compress image and convert to WebP format
    
    Args:
        image_bytes: Raw image bytes
        quality: WebP quality (1-100, default 80)
        max_size: Maximum dimensions (width, height), default (800, 800)
    
    Returns:
        Base64 encoded WebP image string
    """
    try:
        # Open image from bytes
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary (handles RGBA, P, etc.)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Create white background for transparent images
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            if image.mode in ('RGBA', 'LA'):
                background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize image if it's larger than max_size while maintaining aspect ratio
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save as WebP with compression
        webp_buffer = io.BytesIO()
        image.save(webp_buffer, format='WEBP', quality=quality, optimize=True)
        webp_bytes = webp_buffer.getvalue()
        
        # Convert to base64
        base64_webp = base64.b64encode(webp_bytes).decode('utf-8')
        
        return base64_webp
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing image: {str(e)}"
        )


def validate_image_file(file_content: bytes, max_size_mb: int = 10) -> None:
    """
    Validate uploaded image file
    
    Args:
        file_content: Raw file bytes
        max_size_mb: Maximum file size in MB
    """
    # Check file size
    max_size_bytes = max_size_mb * 1024 * 1024
    if len(file_content) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds {max_size_mb}MB limit."
        )
    
    # Try to open as image to validate format
    try:
        image = Image.open(io.BytesIO(file_content))
        image.verify()  # Verify it's a valid image
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image (JPEG, PNG, GIF, BMP, etc.)."
        )


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
            "user_role": "user",  # Set default user role to 'user'
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()  # Store as ISO string
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
async def get_current_user_info(current_user = Depends(get_current_user)):
    """
    Get current authenticated user information
    
    Requires valid JWT token in Authorization header
    """
    # Convert UserInDB to User by removing sensitive data
    user_dict = current_user.dict()
    user_dict.pop("hashed_password", None)
    return User(**user_dict)


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
        
        # Convert datetime to ISO string for backward compatibility
        if "created_at" in user_data and hasattr(user_data["created_at"], "isoformat"):
            user_data["created_at"] = user_data["created_at"].isoformat()
        
        return User(**user_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in get_user_by_id: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.post("/upload-profile", response_model=User)
async def upload_profile_picture(
    user_profile: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """
    Upload and process profile picture for the current user
    
    **Authentication required**: Include JWT token in Authorization header
    
    - **user_profile**: Image file (any common format) - max 10MB
    
    The uploaded image will be:
    - Validated for format and size
    - Compressed and converted to WebP format
    - Resized to max 800x800 pixels (maintaining aspect ratio)
    - Stored as base64 encoded WebP
    
    Returns updated user information with processed profile picture
    """
    try:
        # Read file content
        file_content = await user_profile.read()
        
        # Validate the uploaded file
        validate_image_file(file_content, max_size_mb=10)
        
        # Process image: compress and convert to WebP
        try:
            compressed_webp_base64 = compress_and_convert_to_webp(
                image_bytes=file_content,
                quality=80,  # Good balance between quality and size
                max_size=(800, 800)  # Maximum dimensions
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to process image: {str(e)}"
            )
        
        # Update user in database
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Update user profile picture with processed WebP image
        result = await db.users.update_one(
            {"_id": current_user.id},
            {"$set": {"user_profile": "data:image/webp;base64,"+compressed_webp_base64}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or no changes made"
            )
        
        # Return updated user data
        updated_user_data = await db.users.find_one({"_id": current_user.id})
        if not updated_user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Remove sensitive data
        updated_user_data.pop("hashed_password", None)
        
        # Convert datetime to ISO string for backward compatibility
        if "created_at" in updated_user_data and hasattr(updated_user_data["created_at"], "isoformat"):
            updated_user_data["created_at"] = updated_user_data["created_at"].isoformat()
        
        return User(**updated_user_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in upload_profile_picture: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile picture upload service unavailable"
        )


@router.delete("/remove-profile", response_model=User)
async def remove_profile_picture(current_user = Depends(get_current_user)):
    """
    Remove profile picture for the current user
    
    **Authentication required**: Include JWT token in Authorization header
    
    Returns updated user information without profile picture
    """
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Remove user profile picture
        result = await db.users.update_one(
            {"_id": current_user.id},
            {"$unset": {"user_profile": ""}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or no profile picture to remove"
            )
        
        # Return updated user data
        updated_user_data = await db.users.find_one({"_id": current_user.id})
        if not updated_user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Remove sensitive data
        updated_user_data.pop("hashed_password", None)
        
        # Convert datetime to ISO string for backward compatibility
        if "created_at" in updated_user_data and hasattr(updated_user_data["created_at"], "isoformat"):
            updated_user_data["created_at"] = updated_user_data["created_at"].isoformat()
        
        return User(**updated_user_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in remove_profile_picture: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile picture removal service unavailable"
        ) 