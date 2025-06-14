from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    """User creation model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """User login model"""
    username: str
    password: str


class User(BaseModel):
    """User response model"""
    id: Optional[str] = Field(alias="_id")
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool = True
    created_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserInDB(User):
    """User model with hashed password for database storage"""
    hashed_password: str


class Token(BaseModel):
    """JWT Token response model with refresh token"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Access token expiry in seconds


class TokenData(BaseModel):
    """Token data for JWT payload"""
    username: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Refresh token request model"""
    refresh_token: str


class RefreshTokenData(BaseModel):
    """Refresh token data for JWT payload"""
    username: str
    token_type: str = "refresh" 