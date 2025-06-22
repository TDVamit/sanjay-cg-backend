from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials

from app.core.config import settings
from app.models.user import TokenData, UserInDB, RefreshTokenData
from app.database.mongodb import get_database

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes - both Bearer token and Basic Auth
security_bearer = HTTPBearer()
security_basic = HTTPBasic()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT refresh token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=2)  # 2 days expiry for refresh token
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


async def store_refresh_token(username: str, refresh_token: str):
    """Store refresh token in database for security tracking"""
    try:
        db = await get_database()
        if db is None:
            return  # Graceful degradation if DB unavailable
        
        # Store refresh token with expiry
        refresh_token_doc = {
            "username": username,
            "refresh_token": refresh_token,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=2)
        }
        
        # Upsert refresh token (replace if exists)
        await db.refresh_tokens.replace_one(
            {"username": username},
            refresh_token_doc,
            upsert=True
        )
        
    except Exception as e:
        print(f"Warning: Failed to store refresh token: {e}")
        # Don't raise error, just log it


async def validate_refresh_token(refresh_token: str) -> Optional[str]:
    """Validate refresh token and return username if valid"""
    try:
        # Decode and validate the refresh token
        payload = jwt.decode(refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "refresh":
            return None
        
        # Check if token exists in database (optional security check)
        db = await get_database()
        if db is not None:
            stored_token = await db.refresh_tokens.find_one({
                "username": username,
                "refresh_token": refresh_token,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            if not stored_token:
                return None
        
        return username
        
    except JWTError:
        return None
    except Exception as e:
        print(f"Error validating refresh token: {e}")
        return None


async def revoke_refresh_token(username: str):
    """Revoke/delete refresh token for user"""
    try:
        db = await get_database()
        if db is not None:
            await db.refresh_tokens.delete_one({"username": username})
    except Exception as e:
        print(f"Warning: Failed to revoke refresh token: {e}")


async def get_user(username: str) -> Optional[UserInDB]:
    """Get user from database"""
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        user_data = await db.users.find_one({"username": username})
        if user_data:
            # Ensure _id is a string (it should already be with UUID4)
            if "_id" in user_data:
                user_data["_id"] = str(user_data["_id"])
            
            # Convert datetime to ISO string for backward compatibility
            if "created_at" in user_data and hasattr(user_data["created_at"], "isoformat"):
                user_data["created_at"] = user_data["created_at"].isoformat()
            
            return UserInDB(**user_data)
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in get_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


async def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authenticate user credentials"""
    user = await get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user_bearer(credentials: HTTPAuthorizationCredentials = Depends(security_bearer)) -> UserInDB:
    """Get current authenticated user from JWT Bearer token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "access":
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = await get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_basic(credentials: HTTPBasicCredentials = Depends(security_basic)) -> UserInDB:
    """Get current authenticated user from Basic Auth (username/password)"""
    user = await authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


# Keep the original function for Bearer token (backward compatibility)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_bearer)) -> UserInDB:
    """Get current authenticated user from JWT Bearer token (default method)"""
    return await get_current_user_bearer(credentials) 