from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models.user import UserRole

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: 'UserResponse'

class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    scopes: list[str] = []

class APIKeyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    scopes: list[str] = []
    expires_at: Optional[datetime] = None
    justification: Optional[str] = None

class APIKeyResponse(BaseModel):
    key_id: str
    name: str
    description: Optional[str]
    scopes: list[str]
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    last_used: Optional[datetime]
    usage_count: int

class APIKeyCreateResponse(BaseModel):
    key: str  # The actual API key (only shown once)
    key_info: APIKeyResponse

# Import here to avoid circular imports
from .user import UserResponse

# Forward reference resolution
LoginResponse.model_rebuild()