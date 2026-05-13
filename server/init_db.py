from server.database import Base, engine
from server.models import models

# Create all tables in the engine
Base.metadata.create_all(bind=engine)
print("Database tables created successfully.")
