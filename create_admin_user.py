import asyncio
from database import AsyncSessionLocal
from models import User
from auth import get_password_hash
from sqlalchemy.future import select

async def create_admin():
    async with AsyncSessionLocal() as db:
        # Check if admin exists
        result = await db.execute(select(User).filter(User.username == "admin"))
        user = result.scalars().first()
        
        if user:
            print("User 'admin' already exists.")
            return

        # Create admin user
        hashed_pwd = get_password_hash("password123")
        new_user = User(
            username="admin", 
            hashed_password=hashed_pwd, 
            role="admin"
        )
        db.add(new_user)
        await db.commit()
        print("User 'admin' created successfully with password 'password123'.")

if __name__ == "__main__":
    asyncio.run(create_admin())
