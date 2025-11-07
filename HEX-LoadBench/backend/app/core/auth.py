from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import hashlib
import secrets

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, APIKey

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token scheme
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and return (key, hash)."""
    key = f"hlb_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    return key, key_hash

def verify_api_key(api_key: str, db: Session) -> Optional[APIKey]:
    """Verify an API key and return the corresponding APIKey object."""
    if not api_key.startswith("hlb_"):
        return None
    
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    api_key_obj = db.query(APIKey).filter(
        APIKey.key_hash == key_hash,
        APIKey.is_active == True
    ).first()
    
    if not api_key_obj:
        return None
    
    # Check if key has expired
    if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
        return None
    
    # Update last used
    api_key_obj.last_used = datetime.utcnow()
    api_key_obj.usage_count += 1
    db.commit()
    
    return api_key_obj

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_current_user_from_api_key(
    db: Session = Depends(get_db),
    api_key: str = None
) -> User:
    """Get the current user from API key."""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    
    api_key_obj = verify_api_key(api_key, db)
    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    user = api_key_obj.user
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user

def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise None."""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None

class PermissionChecker:
    """Check user permissions for various actions."""
    
    def __init__(self, required_permissions: list[str]):
        self.required_permissions = required_permissions
    
    def __call__(self, current_user: User = Depends(get_current_active_user)):
        """Check if user has required permissions."""
        user_permissions = self._get_user_permissions(current_user)
        
        for permission in self.required_permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission required: {permission}"
                )
        
        return current_user
    
    def _get_user_permissions(self, user: User) -> list[str]:
        """Get user permissions based on role and subscription."""
        permissions = []
        
        # Base permissions
        if user.role:
            if user.role.value == "admin":
                permissions.extend([
                    "admin:access", "user:create", "user:update", "user:delete",
                    "test:create", "test:update", "test:delete", "test:run",
                    "org:create", "org:update", "org:delete",
                    "system:config", "system:monitor", "emergency:stop"
                ])
            elif user.role.value == "operator":
                permissions.extend([
                    "test:create", "test:update", "test:delete", "test:run",
                    "report:view", "report:export"
                ])
            elif user.role.value == "viewer":
                permissions.extend([
                    "test:view", "report:view"
                ])
        
        # Subscription-based permissions
        if hasattr(user, 'subscriptions') and user.subscriptions:
            subscription = user.subscriptions[0]  # Get active subscription
            if subscription.plan:
                plan_limits = subscription.plan
                if plan_limits.allow_api_access:
                    permissions.append("api:access")
                if plan_limits.allow_advanced_scheduling:
                    permissions.append("test:advanced_schedule")
                if plan_limits.allow_custom_load_profiles:
                    permissions.append("test:custom_profile")
        
        return permissions

# Permission decorators
require_admin = PermissionChecker(["admin:access"])
require_operator = PermissionChecker(["test:create"])
require_test_runner = PermissionChecker(["test:run"])
require_api_access = PermissionChecker(["api:access"])