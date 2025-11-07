from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.auth import get_current_active_user
from app.models.user import User
from app.models.plan import SubscriptionPlan, UserSubscription, get_plan_limits
from app.models.audit import AuditLog, AuditAction, create_audit_log, generate_log_id
from app.schemas.plan import (
    SubscriptionPlanCreate, SubscriptionPlanUpdate, SubscriptionPlanResponse,
    UserSubscriptionCreate, UserSubscriptionUpdate, UserSubscriptionResponse,
    UserSubscriptionWithPlan, UsageReport, PlanChangeRequest, PlanChangeResponse
)
from app.models.user import UserRole

router = APIRouter(prefix="/plans", tags=["subscriptions"])

# Subscription Plan endpoints (admin only)
@router.post("/subscriptions", response_model=SubscriptionPlanResponse)
async def create_subscription_plan(
    plan_data: SubscriptionPlanCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new subscription plan (admin only)."""
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create subscription plans"
        )
    
    # Check if plan already exists
    existing_plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.plan_id == plan_data.plan_id
    ).first()
    
    if existing_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription plan with this ID already exists"
        )
    
    # Create plan
    plan = SubscriptionPlan(**plan_data.dict())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.SUBSCRIPTION_CREATE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="subscription_plan",
        resource_id=plan.plan_id,
        resource_details=plan_data.dict()
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return SubscriptionPlanResponse.from_orm(plan)

@router.get("/subscriptions", response_model=List[SubscriptionPlanResponse])
async def list_subscription_plans(
    public_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List subscription plans."""
    
    query = db.query(SubscriptionPlan)
    
    # Non-admins can only see public plans
    if current_user.role != UserRole.ADMIN:
        query = query.filter(SubscriptionPlan.is_public == True)
    elif public_only:
        query = query.filter(SubscriptionPlan.is_public == True)
    
    # Only active plans
    query = query.filter(SubscriptionPlan.is_active == True)
    
    plans = query.order_by(SubscriptionPlan.monthly_cost).all()
    return [SubscriptionPlanResponse.from_orm(plan) for plan in plans]

@router.get("/subscriptions/{plan_id}", response_model=SubscriptionPlanResponse)
async def get_subscription_plan(
    plan_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific subscription plan."""
    
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.plan_id == plan_id
    ).first()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    
    # Check if user can access this plan
    if not plan.is_public and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this plan"
        )
    
    return SubscriptionPlanResponse.from_orm(plan)

# User Subscription endpoints
@router.post("/subscribe", response_model=UserSubscriptionWithPlan)
async def create_subscription(
    subscription_data: UserSubscriptionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a subscription for the user."""
    
    # Check if plan exists
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.plan_id == subscription_data.plan_id
    ).first()
    
    if not plan or not plan.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    
    # Check if user already has an active subscription
    existing_subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == subscription_data.user_id,
        UserSubscription.status == "active"
    ).first()
    
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has an active subscription"
        )
    
    # Create subscription
    subscription = UserSubscription(
        user_id=subscription_data.user_id,
        organization_id=subscription_data.organization_id or current_user.organization_id,
        plan_id=subscription_data.plan_id,
        billing_cycle=subscription_data.billing_cycle,
        auto_renew=subscription_data.auto_renew,
        start_date=datetime.utcnow()
    )
    
    # Set end date based on billing cycle
    if subscription.billing_cycle == "monthly":
        subscription.end_date = datetime.utcnow() + timedelta(days=30)
    else:  # yearly
        subscription.end_date = datetime.utcnow() + timedelta(days=365)
    
    # Set next billing date
    subscription.next_billing_date = subscription.end_date
    
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    
    # Load plan details
    subscription.plan = plan
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.SUBSCRIPTION_CREATE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="user_subscription",
        resource_id=str(subscription.id),
        resource_details={
            "plan_id": subscription.plan_id,
            "billing_cycle": subscription.billing_cycle
        }
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return UserSubscriptionWithPlan.from_orm(subscription)

@router.get("/my-subscription", response_model=UserSubscriptionWithPlan)
async def get_my_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's subscription."""
    
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == "active"
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )
    
    # Load plan details
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.plan_id == subscription.plan_id
    ).first()
    subscription.plan = plan
    
    return UserSubscriptionWithPlan.from_orm(subscription)

@router.get("/usage", response_model=UsageReport)
async def get_usage_report(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current usage and limits for the user."""
    
    # Get user's subscription
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == "active"
    ).first()
    
    if not subscription:
        # Use free plan limits
        limits = get_plan_limits("free")
    else:
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.plan_id == subscription.plan_id
        ).first()
        
        if plan:
            limits = {
                "max_daily_rps": plan.max_daily_rps,
                "max_concurrent_tests": plan.max_concurrent_tests,
                "max_test_duration": plan.max_test_duration,
                "max_users_per_organization": plan.max_users_per_organization,
                "max_api_keys": plan.max_api_keys
            }
        else:
            limits = get_plan_limits("free")
    
    # Calculate current usage
    from app.schemas.plan import UsageLimits, CurrentUsage
    
    current_usage = CurrentUsage(
        daily_rps=subscription.current_daily_rps if subscription else 0,
        concurrent_tests=subscription.current_concurrent_tests if subscription else 0,
        test_duration=0,  # TODO: Calculate from running tests
        users_in_organization=1,  # TODO: Count users in org
        api_keys_active=1  # TODO: Count active API keys
    )
    
    limits_obj = UsageLimits(**limits)
    
    # Calculate remaining
    remaining = UsageLimits(
        max_daily_rps=max(0, limits_obj.max_daily_rps - current_usage.daily_rps),
        max_concurrent_tests=max(0, limits_obj.max_concurrent_tests - current_usage.concurrent_tests),
        max_test_duration=max(0, limits_obj.max_test_duration - current_usage.test_duration),
        max_users_per_organization=max(0, limits_obj.max_users_per_organization - current_usage.users_in_organization),
        max_api_keys=max(0, limits_obj.max_api_keys - current_usage.api_keys_active)
    )
    
    return UsageReport(
        limits=limits_obj,
        current=current_usage,
        remaining=remaining
    )

@router.post("/change-plan", response_model=PlanChangeResponse)
async def change_subscription_plan(
    change_request: PlanChangeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Change subscription plan."""
    
    # Get current subscription
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == "active"
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )
    
    # Validate new plan
    new_plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.plan_id == change_request.new_plan_id
    ).first()
    
    if not new_plan or not new_plan.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New subscription plan not found"
        )
    
    # Store old plan info
    old_plan_id = subscription.plan_id
    
    # Update subscription
    subscription.plan_id = change_request.new_plan_id
    
    if change_request.immediate_change:
        # Update usage limits immediately
        subscription.next_billing_date = datetime.utcnow()
    
    db.commit()
    db.refresh(subscription)
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.SUBSCRIPTION_UPDATE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="user_subscription",
        resource_id=str(subscription.id),
        resource_details={
            "old_plan_id": old_plan_id,
            "new_plan_id": change_request.new_plan_id,
            "reason": change_request.reason
        }
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return PlanChangeResponse(
        old_plan_id=old_plan_id,
        new_plan_id=change_request.new_plan_id,
        change_date=datetime.utcnow(),
        effective_date=subscription.next_billing_date,
        prorated_charge=None,  # TODO: Calculate prorated charge
        confirmation_id=str(uuid.uuid4())
    )

@router.post("/cancel")
async def cancel_subscription(
    reason: Optional[str] = None,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cancel user's subscription."""
    
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == "active"
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )
    
    # Update subscription status
    subscription.status = "cancelled"
    subscription.auto_renew = False
    db.commit()
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.SUBSCRIPTION_CANCEL,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="user_subscription",
        resource_id=str(subscription.id),
        resource_details={
            "plan_id": subscription.plan_id,
            "reason": reason
        }
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return {"message": "Subscription cancelled successfully"}

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