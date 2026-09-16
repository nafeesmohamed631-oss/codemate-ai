from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class AuthIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

class RegisterIn(BaseModel):
    name: Optional[str] = ""
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    confirm_password: Optional[str] = None

class PreferenceIn(BaseModel):
    technology: str
    knowledge_level: int = Field(ge=5, le=100)
    language: str = "English"
    format: str = "paragraph_and_points"

class ChatIn(BaseModel):
    project_id: int
    question: str = Field(min_length=1, max_length=5000)
    knowledge_level: int = Field(ge=5, le=100)
    language: str = "English"
    format: str = "paragraph_and_points"
    selected_code: Optional[str] = None
