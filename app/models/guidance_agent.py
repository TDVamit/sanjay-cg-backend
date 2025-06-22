from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime


class CategoryInfo(BaseModel):
    """Category information for guidance agent responses"""
    id: str
    name: str


class GuidanceAgentCreate(BaseModel):
    """Guidance agent creation model"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    link: HttpUrl = Field(..., description="URL link to the guidance agent")
    category_ids: Optional[List[str]] = Field(default=[], description="List of category UUIDs")
    profile_pic: Optional[str] = Field(None, description="Base64 encoded profile picture")


class GuidanceAgentUpdate(BaseModel):
    """Guidance agent update model"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    link: Optional[HttpUrl] = Field(None, description="URL link to the guidance agent")
    category_ids: Optional[List[str]] = Field(None, description="List of category UUIDs")
    profile_pic: Optional[str] = Field(None, description="Base64 encoded profile picture")


class GuidanceAgentSummary(BaseModel):
    """Guidance agent summary model for list views"""
    id: str = Field(alias="_id")
    created_at: str  # ISO string format
    updated_at: str  # ISO string format
    name: str
    description: Optional[str] = None
    link: str
    profile_pic: Optional[str] = None
    categories: List[CategoryInfo] = Field(default=[])

    class Config:
        populate_by_name = True


class GuidanceAgent(BaseModel):
    """Full guidance agent response model"""
    id: str = Field(alias="_id")
    created_at: str  # ISO string format
    updated_at: str  # ISO string format
    name: str
    description: Optional[str] = None
    link: str
    profile_pic: Optional[str] = None
    categories: List[CategoryInfo] = Field(default=[])

    class Config:
        populate_by_name = True


class GuidanceAgentInDB(GuidanceAgent):
    """Guidance agent model for database storage"""
    pass


class PaginatedGuidanceAgents(BaseModel):
    """Paginated guidance agents response"""
    items: List[GuidanceAgentSummary]
    total: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool 