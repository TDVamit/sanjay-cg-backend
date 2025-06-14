from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from datetime import datetime
import math

from app.models.category import (
    CategoryCreate, 
    CategoryUpdate, 
    Category, 
    PaginatedCategories
)
from app.models.user import User
from app.database.mongodb import get_database
from app.core.security import get_current_user
from app.core.utils import generate_uuid, is_valid_uuid

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post("/", response_model=Category, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new category
    
    - **name**: Category name (1-100 characters)
    - **description**: Optional description (max 500 characters)
    
    **Authentication required**: Include JWT token in Authorization header
    """
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Check if category name already exists
        existing_category = await db.categories.find_one({"name": category_data.name})
        if existing_category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category with this name already exists"
            )
        
        # Generate UUID for the category
        category_id = generate_uuid()
        current_time = datetime.utcnow()
        
        # Create category document
        category_dict = {
            "_id": category_id,
            "created_at": current_time,
            "updated_at": current_time,
            "name": category_data.name,
            "description": category_data.description,
            "created_by": current_user.username  # Track who created it
        }
        
        # Insert category into database
        result = await db.categories.insert_one(category_dict)
        
        # Remove created_by from response (internal field)
        category_dict.pop("created_by", None)
        
        return Category(**category_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in create_category: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.get("/", response_model=PaginatedCategories)
async def get_all_categories(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    current_user: User = Depends(get_current_user)
):
    """
    Get all categories with pagination
    
    - **page**: Page number (starting from 1)
    - **size**: Number of items per page (1-100)
    - **search**: Optional search term for name and description
    
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
            filter_query = {
                "$or": [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"description": {"$regex": search, "$options": "i"}}
                ]
            }
        
        # Calculate skip value
        skip = (page - 1) * size
        
        # Get total count
        total = await db.categories.count_documents(filter_query)
        
        # Get categories with pagination
        cursor = db.categories.find(filter_query).skip(skip).limit(size).sort("created_at", -1)
        categories_data = await cursor.to_list(length=size)
        
        # Convert to Category models
        categories = []
        for category_dict in categories_data:
            # Remove internal fields
            category_dict.pop("created_by", None)
            categories.append(Category(**category_dict))
        
        # Calculate pagination info
        total_pages = math.ceil(total / size) if total > 0 else 1
        has_next = page < total_pages
        has_prev = page > 1
        
        return PaginatedCategories(
            items=categories,
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
        print(f"Database error in get_all_categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.get("/{category_id}", response_model=Category)
async def get_category(
    category_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific category by ID
    
    - **category_id**: UUID of the category
    
    **Authentication required**: Include JWT token in Authorization header
    """
    if not is_valid_uuid(category_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category ID format. Must be a valid UUID."
        )
    
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        category_data = await db.categories.find_one({"_id": category_id})
        if not category_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        # Remove internal fields
        category_data.pop("created_by", None)
        
        return Category(**category_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in get_category: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.put("/{category_id}", response_model=Category)
async def update_category(
    category_id: str,
    category_update: CategoryUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a specific category
    
    - **category_id**: UUID of the category
    - **name**: New category name (optional)
    - **description**: New description (optional)
    
    **Authentication required**: Include JWT token in Authorization header
    """
    if not is_valid_uuid(category_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category ID format. Must be a valid UUID."
        )
    
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Check if category exists
        existing_category = await db.categories.find_one({"_id": category_id})
        if not existing_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        # Check if new name conflicts with existing category (if name is being updated)
        if category_update.name is not None and category_update.name != existing_category["name"]:
            name_conflict = await db.categories.find_one({"name": category_update.name})
            if name_conflict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category with this name already exists"
                )
        
        # Build update data (only include fields that are provided)
        update_data = {"updated_at": datetime.utcnow()}
        if category_update.name is not None:
            update_data["name"] = category_update.name
        if category_update.description is not None:
            update_data["description"] = category_update.description
        
        # Update the category
        result = await db.categories.update_one(
            {"_id": category_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No changes were made to the category"
            )
        
        # Fetch and return updated category
        updated_category = await db.categories.find_one({"_id": category_id})
        updated_category.pop("created_by", None)
        
        return Category(**updated_category)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in update_category: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.delete("/{category_id}")
async def delete_category(
    category_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a specific category
    
    - **category_id**: UUID of the category
    
    **Authentication required**: Include JWT token in Authorization header
    """
    if not is_valid_uuid(category_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category ID format. Must be a valid UUID."
        )
    
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Check if category exists
        existing_category = await db.categories.find_one({"_id": category_id})
        if not existing_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        # Check if category is being used by any roadmaps
        roadmap_using_category = await db.roadmaps.find_one({"category_ids": category_id})
        if roadmap_using_category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete category that is being used by roadmaps. Remove the category from all roadmaps first."
            )
        
        # Delete the category
        result = await db.categories.delete_one({"_id": category_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete category"
            )
        
        return {
            "message": "Category deleted successfully",
            "category_id": category_id,
            "deleted_by": current_user.username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in delete_category: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        ) 