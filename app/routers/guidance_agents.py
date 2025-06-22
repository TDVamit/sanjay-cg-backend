from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from datetime import datetime
import math

from app.models.guidance_agent import (
    GuidanceAgentCreate,
    GuidanceAgentUpdate,
    GuidanceAgent,
    GuidanceAgentSummary,
    PaginatedGuidanceAgents,
    CategoryInfo
)
from app.models.user import User
from app.database.mongodb import get_database
from app.core.security import get_current_user
from app.core.utils import generate_uuid, is_valid_uuid

router = APIRouter(prefix="/guidance-agents", tags=["Guidance Agents"])


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


def convert_datetime_to_string(data: dict) -> dict:
    """Convert datetime objects to ISO string format"""
    if "created_at" in data and hasattr(data["created_at"], "isoformat"):
        data["created_at"] = data["created_at"].isoformat()
    if "updated_at" in data and hasattr(data["updated_at"], "isoformat"):
        data["updated_at"] = data["updated_at"].isoformat()
    return data


@router.post("/", response_model=GuidanceAgent, status_code=status.HTTP_201_CREATED)
async def create_guidance_agent(
    agent_data: GuidanceAgentCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new guidance agent
    
    - **name**: Agent name (1-200 characters)
    - **description**: Optional description (max 1000 characters)
    - **link**: URL link to the guidance agent
    - **category_ids**: Optional list of category UUIDs
    - **profile_pic**: Optional Base64 encoded profile picture
    
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
        if agent_data.category_ids:
            await validate_category_ids(db, agent_data.category_ids)
        
        # Generate UUID for the guidance agent
        agent_id = generate_uuid()
        current_time = datetime.utcnow()
        
        # Create guidance agent document
        agent_dict = {
            "_id": agent_id,
            "created_at": current_time,
            "updated_at": current_time,
            "name": agent_data.name,
            "description": agent_data.description,
            "link": str(agent_data.link),  # Convert HttpUrl to string
            "profile_pic": agent_data.profile_pic,
            "category_ids": agent_data.category_ids or [],
            "created_by": current_user.username  # Track who created it
        }
        
        # Insert guidance agent into database
        result = await db.guidance_agents.insert_one(agent_dict)
        
        # Get category information for response
        categories = await get_categories_info(db, agent_data.category_ids or [])
        
        # Remove internal fields from response
        agent_dict.pop("created_by", None)
        agent_dict.pop("category_ids", None)
        agent_dict["categories"] = categories
        
        # Convert datetime to string for response
        agent_dict = convert_datetime_to_string(agent_dict)
        
        return GuidanceAgent(**agent_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in create_guidance_agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.get("/", response_model=PaginatedGuidanceAgents)
async def get_all_guidance_agents(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    current_user: User = Depends(get_current_user)
):
    """
    Get all guidance agents with pagination
    
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
        total = await db.guidance_agents.count_documents(filter_query)
        
        # Get guidance agents with pagination
        cursor = db.guidance_agents.find(filter_query).skip(skip).limit(size).sort("created_at", -1)
        agents_data = await cursor.to_list(length=size)
        
        # Convert to GuidanceAgentSummary models with category information
        agents = []
        for agent_dict in agents_data:
            # Remove internal fields
            agent_dict.pop("created_by", None)
            
            # Get category information
            category_ids = agent_dict.get("category_ids", [])
            categories = await get_categories_info(db, category_ids)
            
            # Remove category_ids and add categories
            agent_dict.pop("category_ids", None)
            agent_dict["categories"] = categories
            
            # Convert datetime to string
            agent_dict = convert_datetime_to_string(agent_dict)
            
            agents.append(GuidanceAgentSummary(**agent_dict))
        
        # Calculate pagination info
        total_pages = math.ceil(total / size) if total > 0 else 1
        has_next = page < total_pages
        has_prev = page > 1
        
        return PaginatedGuidanceAgents(
            items=agents,
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
        print(f"Database error in get_all_guidance_agents: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.get("/{agent_id}", response_model=GuidanceAgent)
async def get_guidance_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific guidance agent by ID
    
    - **agent_id**: UUID of the guidance agent
    
    **Authentication required**: Include JWT token in Authorization header
    """
    if not is_valid_uuid(agent_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid guidance agent ID format. Must be a valid UUID."
        )
    
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        agent_data = await db.guidance_agents.find_one({"_id": agent_id})
        if not agent_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guidance agent not found"
            )
        
        # Remove internal fields
        agent_data.pop("created_by", None)
        
        # Get category information
        category_ids = agent_data.get("category_ids", [])
        categories = await get_categories_info(db, category_ids)
        
        # Remove category_ids and add categories
        agent_data.pop("category_ids", None)
        agent_data["categories"] = categories
        
        # Convert datetime to string
        agent_data = convert_datetime_to_string(agent_data)
        
        return GuidanceAgent(**agent_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in get_guidance_agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.put("/{agent_id}", response_model=GuidanceAgent)
async def update_guidance_agent(
    agent_id: str,
    agent_update: GuidanceAgentUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a guidance agent
    
    - **agent_id**: UUID of the guidance agent to update
    - **name**: Optional new name (1-200 characters)
    - **description**: Optional new description (max 1000 characters)
    - **link**: Optional new URL link
    - **category_ids**: Optional new list of category UUIDs
    - **profile_pic**: Optional new Base64 encoded profile picture
    
    **Authentication required**: Include JWT token in Authorization header
    """
    if not is_valid_uuid(agent_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid guidance agent ID format. Must be a valid UUID."
        )
    
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Check if guidance agent exists
        existing_agent = await db.guidance_agents.find_one({"_id": agent_id})
        if not existing_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guidance agent not found"
            )
        
        # Validate category IDs if provided
        if agent_update.category_ids is not None:
            await validate_category_ids(db, agent_update.category_ids)
        
        # Build update data (only include fields that are provided)
        update_data = {"updated_at": datetime.utcnow()}
        if agent_update.name is not None:
            update_data["name"] = agent_update.name
        if agent_update.description is not None:
            update_data["description"] = agent_update.description
        if agent_update.link is not None:
            update_data["link"] = str(agent_update.link)  # Convert HttpUrl to string
        if agent_update.category_ids is not None:
            update_data["category_ids"] = agent_update.category_ids
        if agent_update.profile_pic is not None:
            update_data["profile_pic"] = agent_update.profile_pic
        
        # Update the guidance agent
        result = await db.guidance_agents.update_one(
            {"_id": agent_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No changes were made to the guidance agent"
            )
        
        # Fetch and return updated guidance agent
        updated_agent = await db.guidance_agents.find_one({"_id": agent_id})
        updated_agent.pop("created_by", None)
        
        # Get category information
        category_ids = updated_agent.get("category_ids", [])
        categories = await get_categories_info(db, category_ids)
        
        # Remove category_ids and add categories
        updated_agent.pop("category_ids", None)
        updated_agent["categories"] = categories
        
        # Convert datetime to string
        updated_agent = convert_datetime_to_string(updated_agent)
        
        return GuidanceAgent(**updated_agent)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in update_guidance_agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


@router.delete("/{agent_id}")
async def delete_guidance_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a guidance agent
    
    - **agent_id**: UUID of the guidance agent to delete
    
    **Authentication required**: Include JWT token in Authorization header
    """
    if not is_valid_uuid(agent_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid guidance agent ID format. Must be a valid UUID."
        )
    
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Check if guidance agent exists
        existing_agent = await db.guidance_agents.find_one({"_id": agent_id})
        if not existing_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guidance agent not found"
            )
        
        # Delete the guidance agent
        result = await db.guidance_agents.delete_one({"_id": agent_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete guidance agent"
            )
        
        return {
            "message": "Guidance agent deleted successfully",
            "agent_id": agent_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in delete_guidance_agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        ) 