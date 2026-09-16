from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), default="")
    password_hash = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    kind = Column(String(40), default="file")
    technology = Column(String(80), default="Unknown")
    file_count = Column(Integer, default=1)
    line_count = Column(Integer, default=0)
    status = Column(String(40), default="processing")
    root_path = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="projects")
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")

class ProjectFile(Base):
    __tablename__ = "project_files"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    relative_path = Column(String(1000), nullable=False)
    language = Column(String(80), default="Unknown")
    content = Column(Text, default="")
    line_count = Column(Integer, default=0)
    project = relationship("Project", back_populates="files")

class KnowledgePreference(Base):
    __tablename__ = "knowledge_preferences"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    technology = Column(String(80), nullable=False)
    knowledge_level = Column(Integer, default=20)
    language = Column(String(30), default="English")
    format = Column(String(50), default="paragraph_and_points")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), default="New chat")
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    knowledge_level = Column(Integer)
    language = Column(String(30))
    format = Column(String(50))
    sources = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
