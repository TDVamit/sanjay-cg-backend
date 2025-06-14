from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from datetime import datetime
import math

from app.models.roadmap import (
    RoadmapCreate, 
    RoadmapUpdate, 
    Roadmap, 
    RoadmapSummary,
    PaginatedRoadmaps,
    CategoryInfo
)
from app.models.user import User
from app.database.mongodb import get_database
from app.core.security import get_current_user
from app.core.utils import generate_uuid, is_valid_uuid

router = APIRouter(prefix="/roadmaps", tags=["Roadmaps"])


async def validate_category_ids(db, category_ids: list[str]) -> None:
    """Validate that all category IDs exist in the database"""
    if not category_ids:
        return
    
    for category_id in category_ids:
        if not is_valid_uuid(category_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category ID format: {category_id}. Must be a valid UUID."
            )
    
    # Check if all categories exist
    existing_categories = await db.categories.find({"_id": {"$in": category_ids}}).to_list(length=None)
    existing_ids = {cat["_id"] for cat in existing_categories}
    missing_ids = set(category_ids) - existing_ids
    
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Categories not found: {', '.join(missing_ids)}"
        )


async def get_categories_info(db, category_ids: list[str]) -> list[CategoryInfo]:
    """Fetch category information and return CategoryInfo objects"""
    if not category_ids:
        return []
    
    categories = await db.categories.find({"_id": {"$in": category_ids}}).to_list(length=None)
    return [CategoryInfo(id=cat["_id"], name=cat["name"]) for cat in categories]


@router.post("/", response_model=Roadmap, status_code=status.HTTP_201_CREATED)
async def create_roadmap(
    roadmap_data: RoadmapCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new roadmap
    
    - **name**: Roadmap name (1-200 characters)
    - **roadmap**: Main roadmap content
    - **description**: Optional description (max 1000 characters)
    - **category_ids**: Optional list of category UUIDs
    
    **Authentication required**: Include JWT token in Authorization header
    """
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Validate category IDs if provided
        if roadmap_data.category_ids:
            await validate_category_ids(db, roadmap_data.category_ids)
        
        # Generate UUID for the roadmap
        roadmap_id = generate_uuid()
        current_time = datetime.utcnow()
        
        # Create roadmap document
        roadmap_dict = {
            "_id": roadmap_id,
            "created_at": current_time,
            "updated_at": current_time,
            "name": roadmap_data.name,
            "roadmap": roadmap_data.roadmap,
            "description": roadmap_data.description,
            "category_ids": roadmap_data.category_ids or [],
            "created_by": current_user.username  # Track who created it
        }
        
        # Insert roadmap into database
        result = await db.roadmaps.insert_one(roadmap_dict)
        
        # Get category information for response
        categories = await get_categories_info(db, roadmap_data.category_ids or [])
        
        # Remove created_by from response (internal field)
        roadmap_dict.pop("created_by", None)
        roadmap_dict.pop("category_ids", None)  # Remove category_ids since we're using categories
        roadmap_dict["categories"] = categories
        
        return Roadmap(**roadmap_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in create_roadmap: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.get("/", response_model=PaginatedRoadmaps)
async def get_all_roadmaps(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    current_user: User = Depends(get_current_user)
):
    """
    Get all roadmaps with pagination (without roadmap content)
    
    - **page**: Page number (starting from 1)
    - **size**: Number of items per page (1-100)
    - **search**: Optional search term for name and description
    - **category_id**: Optional category ID to filter by
    
    **Authentication required**: Include JWT token in Authorization header
    """
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Build search filter
        filter_query = {}
        if search:
            filter_query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        
        if category_id:
            if not is_valid_uuid(category_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid category ID format. Must be a valid UUID."
                )
            filter_query["category_ids"] = category_id
        
        # Calculate skip value
        skip = (page - 1) * size
        
        # Get total count
        total = await db.roadmaps.count_documents(filter_query)
        
        # Get roadmaps with pagination, excluding the roadmap content field
        projection = {"roadmap": 0}  # Exclude roadmap content
        cursor = db.roadmaps.find(filter_query, projection).skip(skip).limit(size).sort("created_at", -1)
        roadmaps_data = await cursor.to_list(length=size)
        
        # Convert to RoadmapSummary models with category information
        roadmaps = []
        for roadmap_dict in roadmaps_data:
            # Remove internal fields
            roadmap_dict.pop("created_by", None)
            
            # Get category information
            category_ids = roadmap_dict.get("category_ids", [])
            categories = await get_categories_info(db, category_ids)
            
            # Remove category_ids and add categories
            roadmap_dict.pop("category_ids", None)
            roadmap_dict["categories"] = categories
            
            roadmaps.append(RoadmapSummary(**roadmap_dict))
        
        # Calculate pagination info
        total_pages = math.ceil(total / size) if total > 0 else 1
        has_next = page < total_pages
        has_prev = page > 1
        
        return PaginatedRoadmaps(
            items=roadmaps,
            total=total,
            page=page,
            size=size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in get_all_roadmaps: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.get("/{roadmap_id}", response_model=Roadmap)
async def get_roadmap(
    roadmap_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific roadmap by ID (with full roadmap content)
    
    - **roadmap_id**: UUID of the roadmap
    
    **Authentication required**: Include JWT token in Authorization header
    """
    if not is_valid_uuid(roadmap_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid roadmap ID format. Must be a valid UUID."
        )
    
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        roadmap_data = await db.roadmaps.find_one({"_id": roadmap_id})
        if not roadmap_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Roadmap not found"
            )
        
        # Remove internal fields
        roadmap_data.pop("created_by", None)
        
        # Get category information
        category_ids = roadmap_data.get("category_ids", [])
        categories = await get_categories_info(db, category_ids)
        
        # Remove category_ids and add categories
        roadmap_data.pop("category_ids", None)
        roadmap_data["categories"] = categories
        
        return Roadmap(**roadmap_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in get_roadmap: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.put("/{roadmap_id}", response_model=Roadmap)
async def update_roadmap(
    roadmap_id: str,
    roadmap_update: RoadmapUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a specific roadmap
    
    - **roadmap_id**: UUID of the roadmap
    - **name**: New roadmap name (optional)
    - **roadmap**: New roadmap content (optional)
    - **description**: New description (optional)
    - **category_ids**: New list of category UUIDs (optional)
    
    **Authentication required**: Include JWT token in Authorization header
    """
    if not is_valid_uuid(roadmap_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid roadmap ID format. Must be a valid UUID."
        )
    
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Check if roadmap exists
        existing_roadmap = await db.roadmaps.find_one({"_id": roadmap_id})
        if not existing_roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Roadmap not found"
            )
        
        # Validate category IDs if provided
        if roadmap_update.category_ids is not None:
            await validate_category_ids(db, roadmap_update.category_ids)
        
        # Build update data (only include fields that are provided)
        update_data = {"updated_at": datetime.utcnow()}
        if roadmap_update.name is not None:
            update_data["name"] = roadmap_update.name
        if roadmap_update.roadmap is not None:
            update_data["roadmap"] = roadmap_update.roadmap
        if roadmap_update.description is not None:
            update_data["description"] = roadmap_update.description
        if roadmap_update.category_ids is not None:
            update_data["category_ids"] = roadmap_update.category_ids
        
        # Update the roadmap
        result = await db.roadmaps.update_one(
            {"_id": roadmap_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No changes were made to the roadmap"
            )
        
        # Fetch and return updated roadmap
        updated_roadmap = await db.roadmaps.find_one({"_id": roadmap_id})
        updated_roadmap.pop("created_by", None)
        
        # Get category information
        category_ids = updated_roadmap.get("category_ids", [])
        categories = await get_categories_info(db, category_ids)
        
        # Remove category_ids and add categories
        updated_roadmap.pop("category_ids", None)
        updated_roadmap["categories"] = categories
        
        return Roadmap(**updated_roadmap)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in update_roadmap: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.delete("/{roadmap_id}")
async def delete_roadmap(
    roadmap_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a specific roadmap
    
    - **roadmap_id**: UUID of the roadmap
    
    **Authentication required**: Include JWT token in Authorization header
    """
    if not is_valid_uuid(roadmap_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid roadmap ID format. Must be a valid UUID."
        )
    
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Check if roadmap exists
        existing_roadmap = await db.roadmaps.find_one({"_id": roadmap_id})
        if not existing_roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Roadmap not found"
            )
        
        # Delete the roadmap
        result = await db.roadmaps.delete_one({"_id": roadmap_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete roadmap"
            )
        
        return {
            "message": "Roadmap deleted successfully",
            "roadmap_id": roadmap_id,
            "deleted_by": current_user.username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in delete_roadmap: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        ) 