import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server.database import SessionLocal
from server.models.models import User
from shared.constants import Role
from server.routers.auth import hash_password

def setup():
    db = SessionLocal()
    
    # Clean up old test data
    db.query(User).filter(User.email.in_(["test_examiner@mail.com", "test_student@mail.com"])).delete()
    db.commit()

    # Create Examiner
    examiner = User(
        email="test_examiner@mail.com",
        first_name="Test",
        last_name="Examiner",
        hashed_password=hash_password("password"),
        role=Role.EXAMINER,
    )
    db.add(examiner)
    
    # Create Student
    student = User(
        email="test_student@mail.com",
        first_name="Test",
        last_name="Student",
        hashed_password=hash_password("password"),
        role=Role.STUDENT,
        face_enrolled=True,
    )
    db.add(student)
    db.commit()
    db.close()
    print("Test users created.")

if __name__ == "__main__":
    setup()
