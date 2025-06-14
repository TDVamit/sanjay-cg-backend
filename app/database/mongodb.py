from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from certifi import where
class Database:
    """Database connection handler"""
    client: AsyncIOMotorClient = None
    database = None


db = Database()


async def get_database():
    """Get database instance"""
    return db.database


async def connect_to_mongo():
    """Create database connection"""
    print("🔗 Connecting to MongoDB...")
    
    try:
        # Create client with proper SSL/TLS configuration for MongoDB Atlas
        db.client = AsyncIOMotorClient(
            settings.mongodb_url,
            ssl=True,  # Enable TLS/SSL
            tlsCAFile=where(),
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=10000,  # 10 second connection timeout
            socketTimeoutMS=10000,   # 10 second socket timeout
            maxPoolSize=10,
            retryWrites=True,
            w='majority'  # Write concern
        )
        
        # Test the connection
        await db.client.server_info()
        db.database = db.client[settings.database_name]
        
        print(f"✅ Connected to MongoDB database: {settings.database_name}")
        
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        print("🔄 Starting server without database connection...")
        print("   You can test endpoints that don't require database access")
        # Don't raise the exception to allow the server to start
        # raise


async def close_mongo_connection():
    """Close database connection"""
    if db.client:
        db.client.close()
        print("📡 Disconnected from MongoDB") 