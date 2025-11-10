import sys
import os

# Add app/operations to Python path so 'models' can be found
sys.path.append(os.path.join(os.path.dirname(__file__), "app", "operations"))

from models.calculation import Base
from sqlalchemy import create_engine

# Match your Docker Compose credentials
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/fastapi_db"

engine = create_engine(DATABASE_URL)

# Create tables
Base.metadata.create_all(bind=engine)

print("✅ Tables created successfully.")
