import asyncio
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient("mongodb+srv://effinfinefriday:zoK7WFMVzhCpwWyH@cluster0.iawq3rz.mongodb.net/sanjay-cg?retryWrites=true&w=majority",
tlsCAFile=certifi.where())

async def test_connection():
    try:
        dbs = await client.list_database_names()
        print(dbs)
        print("✅ Connected successfully!")
    except Exception as e:
        print("❌ Failed to connect to MongoDB:", e)

asyncio.run(test_connection())
