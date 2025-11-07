from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.auth import get_current_active_user
from app.models.user import User, Organization, APIKey, UserRole
from app.models.test import TestDefinition, TestExecution, TestStatus
from app.models.plan import SubscriptionPlan, UserSubscription
from app.models.audit import AuditLog
from app.schemas.user import UserResponse, OrganizationResponse
from app.core.config import settings

router = APIRouter(prefix="/admin", tags=["administration"])

# Admin permission decorator
def require_admin(current_user: User = Depends(get_current_active_user)):
    """Require admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required"
        )
    return current_user

# System Overview
@router.get("/overview")
async def get_system_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get system overview statistics."""
    
    # User statistics
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    admin_users = db.query(User).filter(User.role == UserRole.ADMIN).count()
    
    # Organization statistics
    total_organizations = db.query(Organization).count()
    active_organizations = db.query(Organization).filter(Organization.is_active == True).count()
    
    # Test statistics
    total_tests = db.query(TestDefinition).count()
    running_tests = db.query(TestDefinition).filter(TestDefinition.status == TestStatus.RUNNING).count()
    completed_tests = db.query(TestExecution).filter(TestExecution.status == TestStatus.COMPLETED).count()
    
    # API Key statistics
    total_api_keys = db.query(APIKey).count()
    active_api_keys = db.query(APIKey).filter(APIKey.is_active == True).count()
    
    # Subscription statistics
    total_subscriptions = db.query(UserSubscription).filter(
        UserSubscription.status == "active"
    ).count()
    
    # Plan distribution
    plan_distribution = db.query(
        UserSubscription.plan_id,
        func.count(UserSubscription.id).label('count')
    ).filter(UserSubscription.status == "active").group_by(UserSubscription.plan_id).all()
    
    # Recent activity
    recent_audit_logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "admin": admin_users,
            "inactive": total_users - active_users
        },
        "organizations": {
            "total": total_organizations,
            "active": active_organizations,
            "inactive": total_organizations - active_organizations
        },
        "tests": {
            "total": total_tests,
            "running": running_tests,
            "completed": completed_tests,
            "failed": db.query(TestExecution).filter(TestExecution.status == TestStatus.FAILED).count()
        },
        "api_keys": {
            "total": total_api_keys,
            "active": active_api_keys,
            "inactive": total_api_keys - active_api_keys
        },
        "subscriptions": {
            "total": total_subscriptions,
            "distribution": {plan.plan_id: plan.count for plan in plan_distribution}
        },
        "system": {
            "emergency_kill_switch": settings.EMERGENCY_KILL_SWITCH,
            "database_healthy": db.execute("SELECT 1").scalar() == 1,
            "version": settings.VERSION
        },
        "recent_activity": [
            {
                "timestamp": log.timestamp,
                "action": log.action.value,
                "user_email": log.user_email,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id
            }
            for log in recent_audit_logs
        ]
    }

# User Management
@router.get("/users", response_model=List[UserResponse])
async def admin_list_users(
    status: Optional[str] = None,
    role: Optional[UserRole] = None,
    organization_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin endpoint to list all users with filters."""
    
    query = db.query(User)
    
    if status == "active":
        query = query.filter(User.is_active == True)
    elif status == "inactive":
        query = query.filter(User.is_active == False)
    
    if role:
        query = query.filter(User.role == role)
    
    if organization_id:
        query = query.filter(User.organization_id == organization_id)
    
    users = query.offset(offset).limit(limit).all()
    return [UserResponse.from_orm(user) for user in users]

@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Activate a user account."""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already active"
        )
    
    user.is_active = True
    db.commit()
    
    # Log action
    background_tasks.add_task(
        log_admin_action,
        current_user.id,
        "USER_ACTIVATE",
        f"Activated user {user.email}",
        db
    )
    
    return {"message": "User activated successfully"}

@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Deactivate a user account."""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already inactive"
        )
    
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    user.is_active = False
    db.commit()
    
    # Log action
    background_tasks.add_task(
        log_admin_action,
        current_user.id,
        "USER_DEACTIVATE",
        f"Deactivated user {user.email}",
        db
    )
    
    return {"message": "User deactivated successfully"}

# System Configuration
@router.post("/emergency-stop")
async def emergency_stop_all_tests(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Emergency stop all running tests."""
    
    # Find all running tests
    running_tests = db.query(TestDefinition).filter(
        TestDefinition.status == TestStatus.RUNNING
    ).all()
    
    # Stop all tests
    stopped_count = 0
    for test in running_tests:
        test.status = TestStatus.ABORTED
        stopped_count += 1
    
    # Also stop running executions
    running_executions = db.query(TestExecution).filter(
        TestExecution.status == TestStatus.RUNNING
    ).all()
    
    for execution in running_executions:
        execution.status = TestStatus.ABORTED
        execution.abort_reason = "Emergency stop by administrator"
        execution.completed_at = datetime.utcnow()
    
    db.commit()
    
    # Log action
    background_tasks.add_task(
        log_admin_action,
        current_user.id,
        "EMERGENCY_STOP",
        f"Emergency stopped {stopped_count} tests",
        db
    )
    
    return {
        "message": "All running tests stopped",
        "stopped_tests": stopped_count,
        "stopped_executions": len(running_executions)
    }

@router.post("/toggle-emergency-switch")
async def toggle_emergency_switch(
    enable: bool,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Toggle emergency kill switch."""
    
    # This would typically update a config file or database setting
    # For now, we'll just log the action
    action_type = "EMERGENCY_SWITCH_ENABLE" if enable else "EMERGENCY_SWITCH_DISABLE"
    action_message = f"Emergency kill switch {'enabled' if enable else 'disabled'}"
    
    # Log action
    background_tasks.add_task(
        log_admin_action,
        current_user.id,
        action_type,
        action_message,
        db
    )
    
    return {
        "message": action_message,
        "emergency_kill_switch": enable
    }

# Audit Logs
@router.get("/audit-logs")
async def get_audit_logs(
    action_type: Optional[str] = None,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get audit logs with filtering."""
    
    query = db.query(AuditLog)
    
    if action_type:
        query = query.filter(AuditLog.action == action_type)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    
    if start_date:
        query = query.filter(AuditLog.timestamp >= start_date)
    
    if end_date:
        query = query.filter(AuditLog.timestamp <= end_date)
    
    logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
    
    return [
        {
            "log_id": log.log_id,
            "timestamp": log.timestamp,
            "action": log.action.value,
            "user_email": log.user_email,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "ip_address": log.ip_address,
            "success": log.success
        }
        for log in logs
    ]

# System Health
@router.get("/health")
async def get_system_health(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get detailed system health information."""
    
    # Database health
    try:
        db_result = db.execute("SELECT 1").scalar()
        db_healthy = db_result == 1
        
        # Get database size
        if settings.DATABASE_URL.startswith("sqlite"):
            import os
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        else:
            # PostgreSQL
            size_result = db.execute(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            ).scalar()
            db_size = size_result
        
        # Get table counts
        table_counts = {}
        for table_name in ["users", "test_definitions", "test_executions", "audit_logs", "api_keys"]:
            count = db.execute(f"SELECT COUNT(*) FROM {table_name}").scalar()
            table_counts[table_name] = count
            
    except Exception as e:
        db_healthy = False
        db_size = f"Error: {str(e)}"
        table_counts = {}
    
    # Memory usage
    try:
        import psutil
        memory = psutil.virtual_memory()
        memory_usage = {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used
        }
    except ImportError:
        memory_usage = {"error": "psutil not available"}
    
    return {
        "timestamp": datetime.utcnow(),
        "database": {
            "healthy": db_healthy,
            "size": db_size,
            "tables": table_counts
        },
        "memory": memory_usage,
        "settings": {
            "emergency_kill_switch": settings.EMERGENCY_KILL_SWITCH,
            "debug": settings.DEBUG,
            "version": settings.VERSION
        }
    }

# Background task functions
async def log_admin_action(admin_id: int, action: str, message: str, db: Session):
    """Log admin action to audit log."""
    try:
        from app.models.audit import AuditAction, create_audit_log, generate_log_id
        
        admin = db.query(User).filter(User.id == admin_id).first()
        if admin:
            audit_log = create_audit_log(
                action=AuditAction.SYSTEM_CONFIG_CHANGE,
                user_id=admin_id,
                user_email=admin.email,
                organization_id=admin.organization_id,
                resource_type="system",
                resource_id="0",
                resource_details={
                    "action": action,
                    "message": message
                }
            )
            
            log = AuditLog(**audit_log)
            log.log_id = generate_log_id()
            db.add(log)
            db.commit()
    except Exception as e:
        print(f"Failed to log admin action: {e}")