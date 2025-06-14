from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class CategoryInfo(BaseModel):
    """Category information for roadmap responses"""
    id: str
    name: str


class RoadmapCreate(BaseModel):
    """Roadmap creation model"""
    name: str = Field(..., min_length=1, max_length=200)
    roadmap: str = Field(..., min_length=1)
    description: Optional[str] = Field(None, max_length=1000)
    category_ids: Optional[List[str]] = Field(default=[], description="List of category UUIDs")


class RoadmapUpdate(BaseModel):
    """Roadmap update model"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    roadmap: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = Field(None, max_length=1000)
    category_ids: Optional[List[str]] = Field(None, description="List of category UUIDs")


class RoadmapSummary(BaseModel):
    """Roadmap summary model for list views (without roadmap content)"""
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    name: str
    description: Optional[str] = None
    categories: List[CategoryInfo] = Field(default=[])

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Roadmap(BaseModel):
    """Full roadmap response model (with roadmap content)"""
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    name: str
    roadmap: str
    description: Optional[str] = None
    categories: List[CategoryInfo] = Field(default=[])

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RoadmapInDB(Roadmap):
    """Roadmap model for database storage"""
    pass


class PaginatedRoadmaps(BaseModel):
    """Paginated roadmaps response (using summary model)"""
    items: list[RoadmapSummary]
    total: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool 