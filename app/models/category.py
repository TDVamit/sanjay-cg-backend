from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CategoryCreate(BaseModel):
    """Category creation model"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class CategoryUpdate(BaseModel):
    """Category update model"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class Category(BaseModel):
    """Category response model"""
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    name: str
    description: Optional[str] = None

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CategoryInDB(Category):
    """Category model for database storage"""
    pass


class PaginatedCategories(BaseModel):
    """Paginated categories response"""
    items: list[Category]
    total: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool 