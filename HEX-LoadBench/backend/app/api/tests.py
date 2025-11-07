from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from app.core.database import get_db
from app.core.auth import get_current_active_user, require_test_runner
from app.models.user import User
from app.models.test import TestDefinition, TestExecution, TestStatus, LoadProfileType
from app.models.audit import AuditLog, AuditAction, create_audit_log, generate_log_id
from app.schemas.test import (
    TestDefinitionCreate, TestDefinitionUpdate, TestDefinitionResponse,
    TestExecutionResponse, TestStartRequest, TestStopRequest, TestScheduleRequest,
    TestListRequest, TestListResponse, TestSummary
)

router = APIRouter(prefix="/tests", tags=["tests"])

@router.post("/", response_model=TestDefinitionResponse)
async def create_test(
    test_data: TestDefinitionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new test definition."""
    
    # Create test definition
    test_definition = TestDefinition(
        name=test_data.name,
        description=test_data.description,
        target_url=test_data.target_url,
        method=test_data.method,
        headers=test_data.headers,
        body_template=test_data.body_template,
        auth_type=test_data.auth_type,
        auth_credentials=test_data.auth_credentials,
        load_profile_type=test_data.load_profile_type,
        load_profile_config=test_data.load_profile_config.dict(),
        duration=test_data.duration,
        max_concurrent_users=test_data.max_concurrent_users,
        rps_limit=test_data.rps_limit,
        timeout=test_data.timeout,
        region=test_data.region,
        use_proxies=test_data.use_proxies,
        proxy_config=test_data.proxy_config,
        schedule_cron=test_data.schedule_cron,
        test_date=test_data.test_date,
        expiration_date=test_data.expiration_date,
        notify_on_start=test_data.notify_on_start,
        notify_on_complete=test_data.notify_on_complete,
        notify_on_failure=test_data.notify_on_failure,
        notification_channels=test_data.notification_channels,
        authorization_document_hash=test_data.authorization_document_hash,
        justification=test_data.justification,
        created_by=current_user.id
    )
    
    db.add(test_definition)
    db.commit()
    db.refresh(test_definition)
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.TEST_CREATE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="test",
        resource_id=str(test_definition.id),
        resource_details=test_data.dict()
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return TestDefinitionResponse.from_orm(test_definition)

@router.get("/", response_model=TestListResponse)
async def list_tests(
    request: TestListRequest = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List test definitions with pagination and filtering."""
    
    # Build query
    query = db.query(TestDefinition)
    
    # Apply filters
    if request.status:
        query = query.filter(TestDefinition.status == request.status)
    
    if request.created_by:
        query = query.filter(TestDefinition.created_by == request.created_by)
    
    if request.search:
        query = query.filter(TestDefinition.name.ilike(f"%{request.search}%"))
    
    # Apply sorting
    if request.sort_by == "created_at":
        if request.sort_order == "desc":
            query = query.order_by(TestDefinition.created_at.desc())
        else:
            query = query.order_by(TestDefinition.created_at.asc())
    elif request.sort_by == "name":
        if request.sort_order == "desc":
            query = query.order_by(TestDefinition.name.desc())
        else:
            query = query.order_by(TestDefinition.name.asc())
    
    # Count total
    total = query.count()
    
    # Apply pagination
    offset = (request.page - 1) * request.limit
    tests = query.offset(offset).limit(request.limit).all()
    
    # Calculate pages
    pages = (total + request.limit - 1) // request.limit
    
    return TestListResponse(
        tests=[TestDefinitionResponse.from_orm(test) for test in tests],
        total=total,
        page=request.page,
        limit=request.limit,
        pages=pages
    )

@router.get("/{test_id}", response_model=TestDefinitionResponse)
async def get_test(
    test_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific test definition."""
    
    test = db.query(TestDefinition).filter(TestDefinition.id == test_id).first()
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )
    
    return TestDefinitionResponse.from_orm(test)

@router.put("/{test_id}", response_model=TestDefinitionResponse)
async def update_test(
    test_id: int,
    test_data: TestDefinitionUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a test definition."""
    
    test = db.query(TestDefinition).filter(TestDefinition.id == test_id).first()
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )
    
    # Check if test is running
    if test.status == TestStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a running test"
        )
    
    # Update fields
    update_data = test_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(test, field, value)
    
    test.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(test)
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.TEST_UPDATE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="test",
        resource_id=str(test.id),
        resource_details=update_data
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return TestDefinitionResponse.from_orm(test)

@router.delete("/{test_id}")
async def delete_test(
    test_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a test definition."""
    
    test = db.query(TestDefinition).filter(TestDefinition.id == test_id).first()
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )
    
    # Check if test is running
    if test.status == TestStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a running test"
        )
    
    # Store test info for audit
    test_info = TestDefinitionResponse.from_orm(test).dict()
    
    db.delete(test)
    db.commit()
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.TEST_DELETE,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="test",
        resource_id=str(test_id),
        resource_details=test_info
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return {"message": "Test deleted successfully"}

@router.post("/{test_id}/start", response_model=TestExecutionResponse)
async def start_test(
    test_id: int,
    start_request: TestStartRequest = TestStartRequest(),
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_test_runner),
    db: Session = Depends(get_db)
):
    """Start a test execution."""
    
    test = db.query(TestDefinition).filter(TestDefinition.id == test_id).first()
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )
    
    # Check if test is already running
    existing_execution = db.query(TestExecution).filter(
        TestExecution.test_definition_id == test_id,
        TestExecution.status.in_([TestStatus.RUNNING, TestStatus.SCHEDULED])
    ).first()
    
    if existing_execution:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test is already running or scheduled"
        )
    
    # Create test execution
    execution = TestExecution(
        execution_id=str(uuid.uuid4()),
        test_definition_id=test_id,
        status=TestStatus.SCHEDULED,
        config_snapshot=test.dict(),
        allocated_users=test.max_concurrent_users,
        allocated_rps=test.rps_limit,
        runner_type="k6",  # Default runner
        created_by=current_user.id
    )
    
    db.add(execution)
    
    # Update test status
    test.status = TestStatus.RUNNING
    db.commit()
    db.refresh(execution)
    
    # Queue test execution
    background_tasks.add_task(queue_test_execution, execution.id, db)
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.TEST_START,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="test_execution",
        resource_id=execution.execution_id,
        resource_details={
            "test_id": test_id,
            "execution_id": execution.execution_id
        }
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return TestExecutionResponse.from_orm(execution)

@router.post("/{test_id}/stop", response_model=TestExecutionResponse)
async def stop_test(
    test_id: int,
    stop_request: TestStopRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_test_runner),
    db: Session = Depends(get_db)
):
    """Stop/abort a running test."""
    
    # Find running execution
    execution = db.query(TestExecution).filter(
        TestExecution.test_definition_id == test_id,
        TestExecution.status == TestStatus.RUNNING
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No running test found"
        )
    
    # Update execution status
    execution.status = TestStatus.ABORTED
    execution.abort_reason = stop_request.reason
    execution.completed_at = datetime.utcnow()
    
    if execution.started_at:
        execution.duration_actual = int((execution.completed_at - execution.started_at).total_seconds())
    
    db.commit()
    db.refresh(execution)
    
    # Update test status
    test = db.query(TestDefinition).filter(TestDefinition.id == test_id).first()
    if test:
        test.status = TestStatus.ABORTED
        db.commit()
    
    # Create audit log
    audit_log = create_audit_log(
        action=AuditAction.TEST_ABORT,
        user_id=current_user.id,
        user_email=current_user.email,
        organization_id=current_user.organization_id,
        resource_type="test_execution",
        resource_id=execution.execution_id,
        resource_details={
            "test_id": test_id,
            "execution_id": execution.execution_id,
            "reason": stop_request.reason
        }
    )
    
    background_tasks.add_task(log_audit_event, audit_log, db)
    
    return TestExecutionResponse.from_orm(execution)

@router.get("/{test_id}/executions", response_model=List[TestExecutionResponse])
async def get_test_executions(
    test_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all executions for a test."""
    
    # Verify test exists
    test = db.query(TestDefinition).filter(TestDefinition.id == test_id).first()
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )
    
    executions = db.query(TestExecution).filter(
        TestExecution.test_definition_id == test_id
    ).order_by(TestExecution.created_at.desc()).all()
    
    return [TestExecutionResponse.from_orm(execution) for execution in executions]

@router.get("/{test_id}/summary", response_model=TestSummary)
async def get_test_summary(
    test_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get test summary with execution statistics."""
    
    test = db.query(TestDefinition).filter(TestDefinition.id == test_id).first()
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )
    
    # Get execution statistics
    executions = db.query(TestExecution).filter(
        TestExecution.test_definition_id == test_id
    ).all()
    
    total_executions = len(executions)
    successful_executions = len([e for e in executions if e.status == TestStatus.COMPLETED])
    failed_executions = len([e for e in executions if e.status == TestStatus.FAILED])
    
    # Calculate average duration
    completed_executions = [e for e in executions if e.duration_actual is not None]
    average_duration = sum(e.duration_actual for e in completed_executions) / len(completed_executions) if completed_executions else None
    
    # Get last execution
    last_execution = max(executions, key=lambda x: x.created_at) if executions else None
    
    return TestSummary(
        test_definition=TestDefinitionResponse.from_orm(test),
        last_execution=TestExecutionResponse.from_orm(last_execution) if last_execution else None,
        total_executions=total_executions,
        successful_executions=successful_executions,
        failed_executions=failed_executions,
        average_duration=average_duration,
        last_run=last_execution.created_at if last_execution else None
    )

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

async def queue_test_execution(execution_id: int, db: Session):
    """Queue test execution for processing."""
    # This would integrate with the job queue service
    # For now, just mark as running
    execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
    if execution:
        execution.status = TestStatus.RUNNING
        execution.started_at = datetime.utcnow()
        db.commit()
        
        # TODO: Send to job queue service
        print(f"Queued test execution {execution_id} for processing")