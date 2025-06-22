from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.mongodb import connect_to_mongo, close_mongo_connection, get_database
from app.routers import auth, protected, documents, roadmaps, categories, guidance_agents

# Create FastAPI application
app = FastAPI(
    title="FastAPI Authentication System",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(protected.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(roadmaps.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(guidance_agents.router, prefix="/api/v1")

# Database connection events
@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    await connect_to_mongo()


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown"""
    await close_mongo_connection()


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Welcome endpoint
    
    Returns basic API information and available endpoints.
    """
    return {
        "message": "🚀 Welcome to FastAPI Authentication System",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "endpoints": {
            "authentication": "/api/v1/auth",
            "protected_routes": "/api/v1/protected",
            "document_processing": "/api/v1/documents",
            "roadmaps": "/api/v1/roadmaps",
            "categories": "/api/v1/categories",
            "guidance_agents": "/api/v1/guidance-agents"
        },
        "features": [
            "🔐 JWT Authentication",
            "👥 User Management", 
            "📄 PDF Processing",
            "🤖 AI Resume Analysis",
            "📊 ATS Scoring",
            "🗺️ Roadmap Management"
        ]
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns the current status of the API and database connection.
    """
    # Check database connection
    db_status = "disconnected"
    db_error = None
    
    try:
        db = await get_database()
        if db is not None:
            # Try a simple operation
            await db.command("ping")
            db_status = "connected"
    except Exception as e:
        db_error = str(e)
        db_status = "error"
    
    return {
        "status": "healthy",
        "database": db_status,
        "database_error": db_error if db_error else None,
        "version": "1.0.0",
        "features": {
            "authentication": "enabled",
            "document_processing": "enabled",
            "ai_analysis": "enabled"
        }
    }


# Database status endpoint
@app.get("/db-status", tags=["Health"])
async def database_status():
    """
    Database connection status
    
    Returns detailed information about the database connection.
    """
    try:
        db = await get_database()
        if db is None:
            return {
                "status": "disconnected",
                "message": "Database client not initialized",
                "database_name": settings.database_name
            }
        
        # Test database connection
        server_info = await db.client.server_info()
        
        return {
            "status": "connected",
            "database_name": settings.database_name,
            "server_version": server_info.get("version", "unknown"),
            "message": "Database connection is healthy"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "database_name": settings.database_name,
            "message": "Database connection failed"
        } 