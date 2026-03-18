from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON, Integer
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from database import Base

def generate_uuid():
    return uuid.uuid4().hex

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="pm") # admin, pm, designer, qa
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Requirement(Base):
    __tablename__ = "requirements"
    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, index=True)
    description = Column(Text)
    priority = Column(String) # High, Medium, Low
    status = Column(String) # Draft, Review, Approved, etc.
    assignee = Column(String)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # relationship
    test_cases = relationship("TestCase", back_populates="requirement")

class TestCase(Base):
    __tablename__ = "testcases"
    id = Column(String, primary_key=True, default=generate_uuid)
    requirement_id = Column(String, ForeignKey("requirements.id"))
    scenario = Column(String)
    preconditions = Column(Text)
    steps = Column(Text)
    expected_result = Column(Text)
    priority = Column(String)
    script_bound = Column(Boolean, default=False)
    status = Column(String, default="Draft") # Draft, Needs Review, Approved
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    requirement = relationship("Requirement", back_populates="test_cases")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, index=True)
    action = Column(String) # CREATE, UPDATE, DELETE
    resource_type = Column(String) # Requirement, TestCase
    resource_id = Column(String, index=True)
    before_snapshot = Column(JSON, nullable=True)
    after_snapshot = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
