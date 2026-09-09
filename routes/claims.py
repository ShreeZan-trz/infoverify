"""
InfoVerify Claims & Sources Routes
===================================
FastAPI endpoints for claim submission, verification, and source management.

Endpoints:
    POST   /api/claims              - Submit new claim
    GET    /api/claims              - List claims (paginated)
    GET    /api/claims/{claim_id}   - Get claim with full details
    PATCH  /api/claims/{claim_id}/verify - Verify/flag claim
    GET    /api/sources             - List all sources
    POST   /api/sources             - Create new source (admin only)

Usage:
    from routes.claims import router
    app.include_router(router)

Dependencies:
    - database.py (get_db, engine, Base)
    - models.py (all SQLAlchemy models)
    - schemas.py (all Pydantic schemas)
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import (
    APIRouter, Depends, HTTPException, status, Query,
    Path
)
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from pydantic import ValidationError

# Import database
from database import get_db

# Import models
from models import (
    User, Source, Claim, CredibilityScore, VerificationRecord,
    RelatedClaim, AuditLog,
    UserRole, ClaimCategory, VerificationVerdict, AuditAction
)

# Import schemas
from schemas import (
    ClaimCreate, ClaimResponse, ClaimWithScoresResponse, ClaimListResponse,
    CredibilityScoreFull, CredibilityScoreBrief,
    SourceCreate, SourceResponse, SourceListResponse,
    VerificationCreate, VerificationResponse,
    ErrorResponse
)

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create router
router = APIRouter(prefix="/api", tags=["claims", "sources"])

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_claim_or_404(claim_id: UUID, db: Session) -> Claim:
    """
    Retrieve claim by ID or raise 404.
    
    Args:
        claim_id: UUID of claim to retrieve
        db: Database session
        
    Returns:
        Claim: The claim object
        
    Raises:
        HTTPException: 404 if claim not found
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        logger.warning(f"Claim not found: {claim_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found"
        )
    return claim


def get_source_or_404(source_id: UUID, db: Session) -> Source:
    """
    Retrieve source by ID or raise 404.
    
    Args:
        source_id: UUID of source to retrieve
        db: Database session
        
    Returns:
        Source: The source object
        
    Raises:
        HTTPException: 404 if source not found
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        logger.warning(f"Source not found: {source_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {source_id} not found"
        )
    return source


def build_claim_response(claim: Claim, db: Session) -> ClaimWithScoresResponse:
    """
    Build complete claim response with scores and verifications.
    
    Args:
        claim: Claim object from database
        db: Database session
        
    Returns:
        ClaimWithScoresResponse: Full claim with all related data
    """
    # Get credibility score
    score = db.query(CredibilityScore).filter(
        CredibilityScore.claim_id == claim.id
    ).first()
    
    # Get verifications
    verifications = db.query(VerificationRecord).filter(
        VerificationRecord.claim_id == claim.id
    ).all()
    
    # Calculate consensus verdict
    consensus_verdict = None
    if verifications:
        verdict_counts = db.query(
            VerificationRecord.verdict,
            func.count().label("count")
        ).filter(
            VerificationRecord.claim_id == claim.id
        ).group_by(
            VerificationRecord.verdict
        ).order_by(
            func.count().desc()
        ).first()
        
        if verdict_counts:
            consensus_verdict = verdict_counts[0]
    
    # Build source response
    source_response = None
    if claim.source:
        source_response = SourceResponse(
            id=claim.source.id,
            name=claim.source.name,
            source_type=claim.source.source_type,
            credibility_score=claim.source.credibility_score,
            url=claim.source.url,
            created_at=claim.source.created_at,
            updated_at=claim.source.updated_at
        )
    
    # Build complete response
    return ClaimWithScoresResponse(
        id=claim.id,
        content=claim.content,
        category=claim.category,
        source_id=claim.source_id,
        is_processed=claim.is_processed,
        created_at=claim.created_at,
        submitted_by=claim.submitted_by,
        credibility_score=CredibilityScoreFull.from_attributes(score) if score else None,
        verifications_count=len(verifications),
        consensus_verdict=consensus_verdict,
        source=source_response
    )


# ============================================================================
# CLAIMS ENDPOINTS
# ============================================================================

@router.post(
    "/claims",
    response_model=ClaimResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid claim data"},
        404: {"model": ErrorResponse, "description": "Source not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def submit_claim(
    claim_create: ClaimCreate,
    db: Session = Depends(get_db)
) -> ClaimResponse:
    """
    Submit a new claim for fact-checking.
    
    Creates a new claim record and saves it to the database. Claims are
    initially marked as unprocessed and will receive credibility scores
    from the scoring pipeline.
    
    **Request body:**
    - `content`: Claim text (1-10,000 characters) - **REQUIRED**
    - `source_id`: UUID of information source - **REQUIRED**
    - `source_url`: Direct URL to original claim (optional)
    - `category`: Domain category (politics, health, finance, disaster, science, other)
    
    **Responses:**
    - `201 Created`: Claim successfully created
    - `400 Bad Request`: Invalid claim data (validation error)
    - `404 Not Found`: Source does not exist
    - `500 Internal Server Error`: Database error
    
    **Example:**
    ```json
    {
      "content": "COVID-19 vaccines contain microchips",
      "source_id": "550e8400-e29b-41d4-a716-446655440000",
      "source_url": "https://twitter.com/misinformation/123",
      "category": "health"
    }
    ```
    """
    try:
        logger.info(f"Submitting claim: category={claim_create.category}")
        
        # Verify source exists
        source = db.query(Source).filter(Source.id == claim_create.source_id).first()
        if not source:
            logger.warning(f"Source not found: {claim_create.source_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {claim_create.source_id} not found"
            )
        
        # TODO: Get current user from JWT token
        # For now, use first admin user for testing
        current_user = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not current_user:
            logger.error("No admin user found for claim submission")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No authorized user found for claim submission"
            )
        
        # Create claim
        db_claim = Claim(
            content=claim_create.content,
            source_id=claim_create.source_id,
            submitted_by=current_user.id,
            category=claim_create.category,
            source_url=claim_create.source_url
        )
        
        db.add(db_claim)
        db.flush()  # Get the ID before commit
        
        # Log to audit trail
        audit_log = AuditLog(
            user_id=current_user.id,
            action=AuditAction.SUBMITTED_CLAIM,
            resource_type="claim",
            resource_id=db_claim.id,
            details={
                "category": claim_create.category.value,
                "source_id": str(claim_create.source_id)
            }
        )
        db.add(audit_log)
        
        db.commit()
        db.refresh(db_claim)
        
        logger.info(f"Claim created: id={db_claim.id}, category={claim_create.category}")
        
        return ClaimResponse(
            id=db_claim.id,
            content=db_claim.content,
            category=db_claim.category,
            source_id=db_claim.source_id,
            is_processed=db_claim.is_processed,
            created_at=db_claim.created_at,
            submitted_by=db_claim.submitted_by
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValidationError as e:
        logger.error(f"Validation error in submit_claim: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error submitting claim: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while submitting claim"
        )


@router.get(
    "/claims",
    response_model=ClaimListResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_claims(
    skip: int = Query(0, ge=0, description="Number of claims to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum claims to return"),
    category: Optional[str] = Query(
        None,
        description="Filter by category (politics, health, finance, disaster, science, other)"
    ),
    is_processed: Optional[bool] = Query(
        None,
        description="Filter by processing status (true/false)"
    ),
    db: Session = Depends(get_db)
) -> ClaimListResponse:
    """
    List all claims with pagination and optional filtering.
    
    Returns paginated list of claims ordered by newest first. Can filter
    by category and processing status.
    
    **Query parameters:**
    - `skip`: Number of records to skip (default: 0)
    - `limit`: Max records to return, 1-100 (default: 20)
    - `category`: Filter by claim category (optional)
    - `is_processed`: Filter by processing status (optional)
    
    **Responses:**
    - `200 OK`: List of claims with pagination info
    - `400 Bad Request`: Invalid query parameters
    - `500 Internal Server Error`: Database error
    
    **Example:**
    ```
    GET /api/claims?skip=0&limit=20&category=health&is_processed=false
    ```
    """
    try:
        logger.info(f"Listing claims: skip={skip}, limit={limit}, category={category}")
        
        # Build base query
        query = db.query(Claim)
        
        # Apply filters
        if category:
            try:
                category_enum = ClaimCategory[category.upper()]
                query = query.filter(Claim.category == category_enum)
            except KeyError:
                logger.warning(f"Invalid category: {category}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid category: {category}. Must be one of: {', '.join([c.value for c in ClaimCategory])}"
                )
        
        if is_processed is not None:
            query = query.filter(Claim.is_processed == is_processed)
        
        # Get total count (before pagination)
        total = query.count()
        
        # Get paginated results (newest first)
        claims = query.order_by(desc(Claim.created_at)).offset(skip).limit(limit).all()
        
        # Build response items with credibility scores
        items = []
        for claim in claims:
            try:
                response = build_claim_response(claim, db)
                items.append(response)
            except Exception as e:
                logger.error(f"Error building response for claim {claim.id}: {e}")
                # Continue with other claims
                continue
        
        logger.info(f"Listed {len(items)} claims out of {total} total")
        
        return ClaimListResponse(
            total=total,
            limit=limit,
            offset=skip,
            items=items
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing claims: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while listing claims"
        )


@router.get(
    "/claims/{claim_id}",
    response_model=ClaimWithScoresResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Claim not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_claim(
    claim_id: UUID = Path(..., description="UUID of the claim to retrieve"),
    db: Session = Depends(get_db)
) -> ClaimWithScoresResponse:
    """
    Get a single claim with all details.
    
    Returns complete claim information including:
    - Claim content and metadata
    - Credibility score (if available)
    - All verification records from human verifiers
    - Consensus verdict
    - Related/contradicting claims
    - Source information
    
    **Path parameters:**
    - `claim_id`: UUID of the claim
    
    **Responses:**
    - `200 OK`: Complete claim details
    - `404 Not Found`: Claim does not exist
    - `500 Internal Server Error`: Database error
    
    **Example:**
    ```
    GET /api/claims/550e8400-e29b-41d4-a716-446655440001
    ```
    """
    try:
        logger.info(f"Getting claim: {claim_id}")
        
        # Get claim or raise 404
        claim = get_claim_or_404(claim_id, db)
        
        # Build and return response
        response = build_claim_response(claim, db)
        
        logger.info(f"Retrieved claim: {claim_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting claim {claim_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving claim"
        )


@router.patch(
    "/claims/{claim_id}/verify",
    response_model=VerificationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid verification data"},
        403: {"model": ErrorResponse, "description": "Unauthorized (verifier role required)"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def verify_claim(
    claim_id: UUID = Path(..., description="UUID of the claim to verify"),
    verification_create: VerificationCreate = ...,
    db: Session = Depends(get_db)
) -> VerificationResponse:
    """
    Submit verification verdict for a claim.
    
    Creates a verification record documenting human fact-checker's assessment
    of a claim's veracity. Multiple verifications per claim allowed for
    consensus building.
    
    **Path parameters:**
    - `claim_id`: UUID of the claim to verify
    
    **Request body:**
    - `verdict`: Assessment outcome - **REQUIRED**
      - `confirmed_true`: Verified as true
      - `confirmed_false`: Verified as false
      - `misleading`: Partially true or misleading
      - `needs_more_info`: Insufficient evidence
    - `confidence_level`: Verifier confidence 1-5 - **REQUIRED**
      - 1 = minimal confidence
      - 5 = complete certainty
    - `notes`: Investigation details and evidence sources (optional, max 5000 chars)
    
    **Responses:**
    - `201 Created`: Verification recorded successfully
    - `400 Bad Request`: Invalid verification data
    - `403 Forbidden`: User lacks verifier role
    - `404 Not Found`: Claim not found
    - `500 Internal Server Error`: Database error
    
    **Example:**
    ```json
    {
      "verdict": "confirmed_false",
      "confidence_level": 5,
      "notes": "Verified through CDC and WHO sources. No evidence of microchips."
    }
    ```
    
    **Note:** Currently open to all users. Authentication will be added
    to restrict to verifier/admin roles.
    """
    try:
        logger.info(f"Verifying claim: {claim_id}, verdict={verification_create.verdict}")
        
        # Verify claim exists
        claim = get_claim_or_404(claim_id, db)
        
        # TODO: Get current user from JWT token
        # For now, use first verifier/admin user for testing
        current_user = db.query(User).filter(
            User.role.in_([UserRole.VERIFIER, UserRole.ADMIN])
        ).first()
        if not current_user:
            logger.error("No verifier user found")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only verifiers can create verification records"
            )
        
        # Validate confidence level (redundant due to Pydantic, but explicit)
        if not (1 <= verification_create.confidence_level <= 5):
            logger.warning(f"Invalid confidence level: {verification_create.confidence_level}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Confidence level must be between 1 and 5"
            )
        
        # Create verification record
        db_verification = VerificationRecord(
            claim_id=claim_id,
            verified_by=current_user.id,
            verdict=verification_create.verdict,
            confidence_level=verification_create.confidence_level,
            notes=verification_create.notes
        )
        
        db.add(db_verification)
        db.flush()
        
        # Log to audit trail
        audit_log = AuditLog(
            user_id=current_user.id,
            action=AuditAction.VERIFIED_CLAIM,
            resource_type="verification",
            resource_id=db_verification.id,
            details={
                "claim_id": str(claim_id),
                "verdict": verification_create.verdict.value,
                "confidence": verification_create.confidence_level
            }
        )
        db.add(audit_log)
        
        db.commit()
        db.refresh(db_verification)
        
        logger.info(f"Verification created: id={db_verification.id}, verdict={verification_create.verdict}")
        
        return VerificationResponse(
            id=db_verification.id,
            claim_id=db_verification.claim_id,
            verdict=db_verification.verdict,
            confidence_level=db_verification.confidence_level,
            verified_by=db_verification.verified_by,
            verified_at=db_verification.verified_at,
            verifier_username=current_user.username
        )
        
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(f"Validation error in verify_claim: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error verifying claim {claim_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while verifying claim"
        )


# ============================================================================
# SOURCES ENDPOINTS
# ============================================================================

@router.get(
    "/sources",
    response_model=SourceListResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_sources(
    skip: int = Query(0, ge=0, description="Number of sources to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum sources to return"),
    db: Session = Depends(get_db)
) -> SourceListResponse:
    """
    List all information sources.
    
    Returns paginated list of all registered information sources (news outlets,
    social media platforms, blogs, forums, official sources, etc).
    
    **Query parameters:**
    - `skip`: Number of records to skip (default: 0)
    - `limit`: Max records to return, 1-100 (default: 50)
    
    **Responses:**
    - `200 OK`: List of sources with pagination info
    - `500 Internal Server Error`: Database error
    
    **Example:**
    ```
    GET /api/sources?skip=0&limit=50
    ```
    """
    try:
        logger.info(f"Listing sources: skip={skip}, limit={limit}")
        
        # Get total count
        total = db.query(func.count(Source.id)).scalar()
        
        # Get paginated results
        sources = db.query(Source).offset(skip).limit(limit).all()
        
        # Convert to response schemas
        items = [
            SourceResponse(
                id=source.id,
                name=source.name,
                source_type=source.source_type,
                credibility_score=source.credibility_score,
                url=source.url,
                created_at=source.created_at,
                updated_at=source.updated_at
            )
            for source in sources
        ]
        
        logger.info(f"Listed {len(items)} sources out of {total} total")
        
        return SourceListResponse(
            total=total or 0,
            limit=limit,
            offset=skip,
            items=items
        )
        
    except Exception as e:
        logger.error(f"Error listing sources: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while listing sources"
        )


@router.post(
    "/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid source data"},
        403: {"model": ErrorResponse, "description": "Unauthorized (admin role required)"},
        409: {"model": ErrorResponse, "description": "Source name already exists"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def create_source(
    source_create: SourceCreate,
    db: Session = Depends(get_db)
) -> SourceResponse:
    """
    Create a new information source.
    
    Registers a new source (news outlet, social media, blog, forum, etc)
    in the system. Sources are used to track claim origins and their
    historical credibility.
    
    **Authorization:** Admin role required (currently open for testing)
    
    **Request body:**
    - `name`: Unique source name (e.g., "CNN", "Twitter") - **REQUIRED**
    - `source_type`: Classification (social_media, news, blog, forum, official, eyewitness) - **REQUIRED**
    - `credibility_score`: Base credibility 0.0-1.0 (default: 0.5) - **REQUIRED**
    - `url`: Homepage URL (optional)
    - `description`: Human-readable description (optional)
    
    **Responses:**
    - `201 Created`: Source successfully created
    - `400 Bad Request`: Invalid source data
    - `403 Forbidden`: User lacks admin role
    - `409 Conflict`: Source name already exists
    - `500 Internal Server Error`: Database error
    
    **Example:**
    ```json
    {
      "name": "CNN Breaking News",
      "source_type": "news",
      "credibility_score": 0.75,
      "url": "https://cnn.com",
      "description": "CNN international news network"
    }
    ```
    
    **Note:** Currently open to all users. Authentication will be added
    to restrict to admin role only.
    """
    try:
        logger.info(f"Creating source: name={source_create.name}, type={source_create.source_type}")
        
        # TODO: Verify admin role from JWT token
        # For now, open to all users for testing
        
        # Check if source name already exists
        existing = db.query(Source).filter(Source.name == source_create.name).first()
        if existing:
            logger.warning(f"Source already exists: {source_create.name}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Source '{source_create.name}' already exists"
            )
        
        # Validate credibility score (redundant due to Pydantic, but explicit)
        if not (0.0 <= source_create.credibility_score <= 1.0):
            logger.warning(f"Invalid credibility score: {source_create.credibility_score}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credibility score must be between 0.0 and 1.0"
            )
        
        # Create source
        db_source = Source(
            name=source_create.name,
            source_type=source_create.source_type,
            credibility_score=source_create.credibility_score,
            url=source_create.url,
            description=source_create.description
        )
        
        db.add(db_source)
        
        # TODO: Log source creation to audit trail
        # current_user = get current user from JWT
        # audit_log = AuditLog(
        #     user_id=current_user.id,
        #     action=AuditAction.CREATED_SOURCE,
        #     resource_type="source",
        #     resource_id=db_source.id,
        #     details={"source_type": source_create.source_type.value}
        # )
        # db.add(audit_log)
        
        db.commit()
        db.refresh(db_source)
        
        logger.info(f"Source created: id={db_source.id}, name={source_create.name}")
        
        return SourceResponse(
            id=db_source.id,
            name=db_source.name,
            source_type=db_source.source_type,
            credibility_score=db_source.credibility_score,
            url=db_source.url,
            created_at=db_source.created_at,
            updated_at=db_source.updated_at
        )
        
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(f"Validation error in create_source: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error creating source: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while creating source"
        )


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@router.get("/health", tags=["system"])
async def health_check() -> dict:
    """
    Health check endpoint.
    
    Returns:
        dict: Status and timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "infoverify-api"
    }
