from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.auth import (
    get_current_active_user, 
    get_password_hash, 
    generate_api_key,
    verify_api_key
)
from app.models.user import User, Organization, APIKey, UserRole
from app.models.audit import AuditLog, AuditAction, create_audit_log, generate_log_id
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserWithSubscription,
    OrganizationCreate, OrganizationUpdate, OrganizationResponse, OrganizationWithUsers
)
from app.schemas.auth import APIKeyCreate, APIKeyResponse, APIKeyCreateResponse

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new user (admin only)."""
    
    # Check permissions (only admins can create users)
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create users"
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()
    
    if existing_user:
        if existing_user.email == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Create user
    user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        is_active=user_data.is_active,
        organization_id=current_user.organization_id,  # Add to same org as creator
        created_by=current_user.id
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.USER_CREATE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="user",
        resource_id=str(user.id),
        resource_details={
            "email": user.email,
            "username": user.username,
            "role": user.role.value
        }
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return UserResponse.from_orm(user)

@router.get("/me", response_model=UserWithSubscription)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user information with subscription."""
    
    # Load subscription if exists
    subscription = None
    if hasattr(current_user, 'subscriptions') and current_user.subscriptions:
        from app.schemas.plan import UserSubscriptionWithPlan
        subscription = UserSubscriptionWithPlan.from_orm(current_user.subscriptions[0])
    
    user_data = UserResponse.from_orm(current_user)
    return UserWithSubscription(**user_data.dict(), subscription=subscription)

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user information."""
    
    # Users can update their own profile (except role)
    update_data = user_data.dict(exclude_unset=True)
    if 'role' in update_data and current_user.role != UserRole.ADMIN:
        del update_data['role']  # Non-admins cannot change their role
    
    # Store old values for audit
    old_values = {
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name
    }
    
    # Update user
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    current_user.updated_at = current_user.updated_at
    db.commit()
    db.refresh(current_user)
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.USER_UPDATE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="user",
        resource_id=str(current_user.id),
        resource_details={
            "old_values": old_values,
            "new_values": update_data
        }
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return UserResponse.from_orm(current_user)

@router.get("/", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all users in the organization."""
    
    # Filter by organization
    query = db.query(User).filter(User.organization_id == current_user.organization_id)
    
    # Non-admins can only see themselves
    if current_user.role != UserRole.ADMIN:
        query = query.filter(User.id == current_user.id)
    
    users = query.all()
    return [UserResponse.from_orm(user) for user in users]

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific user."""
    
    # Users can only view their own profile unless they're admin
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_orm(user)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a user (admin only)."""
    
    # Only admins can update other users
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update users"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Store old values for audit
    old_values = {
        "email": user.email,
        "username": user.username,
        "role": user.role.value,
        "is_active": user.is_active
    }
    
    # Update user
    update_data = user_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_at = user.updated_at
    db.commit()
    db.refresh(user)
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.USER_UPDATE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="user",
        resource_id=str(user.id),
        resource_details={
            "old_values": old_values,
            "new_values": update_data
        }
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return UserResponse.from_orm(user)

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)."""
    
    # Only admins can delete users
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete users"
        )
    
    # Cannot delete yourself
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Store user info for audit
    user_info = UserResponse.from_orm(user).dict()
    
    db.delete(user)
    db.commit()
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.USER_DELETE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="user",
        resource_id=str(user_id),
        resource_details=user_info
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return {"message": "User deleted successfully"}

# API Key endpoints
@router.post("/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new API key for the user."""
    
    # Check user's API key limit
    existing_keys = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.is_active == True
    ).count()
    
    # TODO: Check subscription limits
    if existing_keys >= 3:  # Default limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key limit exceeded"
        )
    
    # Generate API key
    api_key, key_hash = generate_api_key()
    key_id = str(uuid.uuid4())
    
    # Create API key record
    api_key_obj = APIKey(
        key_id=key_id,
        key_hash=key_hash,
        name=key_data.name,
        description=key_data.description,
        scopes=",".join(key_data.scopes),
        expires_at=key_data.expires_at,
        justification=key_data.justification,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        created_by=current_user.id
    )
    
    db.add(api_key_obj)
    db.commit()
    db.refresh(api_key_obj)
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.API_KEY_CREATE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="api_key",
        resource_id=key_id,
        resource_details={
            "name": key_data.name,
            "scopes": key_data.scopes
        }
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return APIKeyCreateResponse(
        key=api_key,
        key_info=APIKeyResponse(
            key_id=api_key_obj.key_id,
            name=api_key_obj.name,
            description=api_key_obj.description,
            scopes=api_key_obj.scopes.split(",") if api_key_obj.scopes else [],
            is_active=api_key_obj.is_active,
            expires_at=api_key_obj.expires_at,
            created_at=api_key_obj.created_at,
            last_used=api_key_obj.last_used,
            usage_count=api_key_obj.usage_count
        )
    )

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's API keys."""
    
    api_keys = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.is_active == True
    ).all()
    
    return [
        APIKeyResponse(
            key_id=key.key_id,
            name=key.name,
            description=key.description,
            scopes=key.scopes.split(",") if key.scopes else [],
            is_active=key.is_active,
            expires_at=key.expires_at,
            created_at=key.created_at,
            last_used=key.last_used,
            usage_count=key.usage_count
        )
        for key in api_keys
    ]

@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete (deactivate) an API key."""
    
    api_key = db.query(APIKey).filter(
        APIKey.key_id == key_id,
        APIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Deactivate instead of delete for audit purposes
    api_key.is_active = False
    db.commit()
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.API_KEY_DELETE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="api_key",
        resource_id=key_id,
        resource_details={
            "name": api_key.name
        }
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return {"message": "API key deactivated successfully"}

# Background task functions
async def log_audit_event(audit_data: dict, db: Session):
    """Log audit event to database."""
    try:
        audit_log = AuditLog(**audit_data)
        audit_log.log_id = generate_log_id()
        db.add(audit_log)
        db.commit()
    except Exception as e:
        print(f"Failed to log audit event: {e}")

# Import required modules
import uuid