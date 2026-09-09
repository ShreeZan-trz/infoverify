"""
InfoVerify Pydantic Schemas
===========================
Request/response validation schemas for FastAPI endpoints.

Used for:
- Request body validation
- Response serialization
- API documentation (OpenAPI/Swagger)
- Type hints in route handlers

Config:
    from_attributes = True  # SQLAlchemy ORM mode for easy conversion
    json_schema_extra = {   # Add examples to OpenAPI docs
        "example": {...}
    }
"""

from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator

from models import (
    UserRole, SourceType, ClaimCategory, VerificationVerdict,
    RelationshipType, AuditAction
)

# ============================================================================
# USER SCHEMAS
# ============================================================================

class UserCreate(BaseModel):
    """
    User creation request schema.
    
    Used when registering a new user. Password is hashed server-side.
    
    Attributes:
        email: Valid email address (unique in system)
        username: 3-100 character alphanumeric string (unique)
        password: At least 8 characters for security
        role: User role (defaults to 'viewer')
    """
    email: EmailStr = Field(
        ...,
        description="Email address for authentication",
        examples=["analyst@infoverify.io"]
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Unique display name",
        examples=["alice_analyst"]
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (hashed with Bcrypt/Argon2 server-side)",
        examples=["SecurePassword123!"]
    )
    role: UserRole = Field(
        default=UserRole.VIEWER,
        description="User role (viewer, analyst, verifier, admin)"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "email": "analyst@infoverify.io",
                "username": "alice_analyst",
                "password": "SecurePassword123!",
                "role": "analyst"
            }
        }


class UserResponse(BaseModel):
    """
    User response schema (no password).
    
    Returned by GET endpoints. Never includes password_hash.
    
    Attributes:
        id: UUID identifier
        email: User's email address
        username: User's display name
        role: User's access level
        is_active: Whether user can authenticate
        last_login_at: Most recent successful login
        created_at: Account creation timestamp
    """
    id: UUID = Field(..., description="Unique user identifier (UUID v4)")
    email: str = Field(..., description="Email address", examples=["analyst@infoverify.io"])
    username: str = Field(..., description="Display name", examples=["alice_analyst"])
    role: UserRole = Field(..., description="User role")
    is_active: bool = Field(
        ...,
        description="Whether user is active (can authenticate)"
    )
    last_login_at: Optional[datetime] = Field(
        None,
        description="Timestamp of most recent successful login"
    )
    created_at: datetime = Field(..., description="Account creation timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "analyst@infoverify.io",
                "username": "alice_analyst",
                "role": "analyst",
                "is_active": True,
                "last_login_at": "2024-01-15T10:30:00Z",
                "created_at": "2024-01-01T09:00:00Z"
            }
        }


class UserUpdate(BaseModel):
    """
    User update request schema.
    
    All fields are optional. Only provided fields are updated.
    
    Attributes:
        email: New email address (optional)
        username: New username (optional)
        password: New password (optional)
    """
    email: Optional[EmailStr] = Field(
        None,
        description="New email address"
    )
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
        description="New username"
    )
    password: Optional[str] = Field(
        None,
        min_length=8,
        max_length=128,
        description="New password (will be hashed)"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "email": "newemail@infoverify.io",
                "username": "alice_v2"
            }
        }


# ============================================================================
# SOURCE SCHEMAS
# ============================================================================

class SourceCreate(BaseModel):
    """
    Source creation request schema.
    
    Registers a new information source (Twitter, CNN, Reddit, etc).
    
    Attributes:
        name: Unique name of source
        source_type: Classification (social_media, news, blog, forum, official, eyewitness)
        credibility_score: Base credibility [0.0, 1.0]
        url: Homepage URL (optional)
        description: Human-readable description (optional)
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique name of source",
        examples=["CNN Breaking News"]
    )
    source_type: SourceType = Field(
        ...,
        description="Source classification"
    )
    credibility_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Base credibility score [0.0, 1.0]"
    )
    url: Optional[str] = Field(
        None,
        max_length=2048,
        description="Homepage URL",
        examples=["https://cnn.com"]
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Human-readable description"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "name": "CNN Breaking News",
                "source_type": "news",
                "credibility_score": 0.75,
                "url": "https://cnn.com",
                "description": "CNN international news network"
            }
        }


class SourceResponse(BaseModel):
    """
    Source response schema.
    
    Attributes:
        id: UUID identifier
        name: Source name
        source_type: Source classification
        credibility_score: Current credibility score
        url: Homepage URL
        created_at: Registration timestamp
        updated_at: Last update timestamp
    """
    id: UUID = Field(..., description="Unique source identifier")
    name: str = Field(..., description="Source name")
    source_type: SourceType = Field(..., description="Source classification")
    credibility_score: float = Field(..., description="Credibility score [0.0, 1.0]")
    url: Optional[str] = Field(None, description="Homepage URL")
    created_at: datetime = Field(..., description="Registration timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "CNN Breaking News",
                "source_type": "news",
                "credibility_score": 0.75,
                "url": "https://cnn.com",
                "created_at": "2024-01-01T09:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }


class SourceListResponse(BaseModel):
    """Paginated list of sources"""
    total: int = Field(..., description="Total number of sources")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Pagination offset")
    items: List[SourceResponse] = Field(..., description="Sources in this page")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "total": 150,
                "limit": 50,
                "offset": 0,
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "CNN",
                        "source_type": "news",
                        "credibility_score": 0.75,
                        "url": "https://cnn.com",
                        "created_at": "2024-01-01T09:00:00Z",
                        "updated_at": "2024-01-15T10:30:00Z"
                    }
                ]
            }
        }


# ============================================================================
# CREDIBILITY SCORE SCHEMAS
# ============================================================================

class CredibilityScoreBrief(BaseModel):
    """
    Brief credibility score (overall score only).
    
    Used in responses where detailed breakdown isn't needed.
    
    Attributes:
        overall_score: Composite credibility [0.0, 1.0]
        calculated_by: Algorithm that calculated score
    """
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite credibility score"
    )
    calculated_by: str = Field(..., description="Algorithm identifier")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "overall_score": 0.15,
                "calculated_by": "nlp-v2.1"
            }
        }


class CredibilityScoreFull(BaseModel):
    """
    Full credibility score breakdown.
    
    Includes all 5 dimensional scores and reasoning.
    
    Attributes:
        id: UUID identifier
        claim_id: Foreign key to claim
        overall_score: Composite credibility [0.0, 1.0]
        language_score: Sensationalism/emotional language detection
        source_score: Source credibility score
        consistency_score: Alignment with verified claims
        verifiability_score: Falsifiability assessment
        reasoning: Human-readable explanation
        calculated_by: Algorithm version identifier
        calculated_at: When scoring was performed
    """
    id: UUID = Field(..., description="Unique score identifier")
    claim_id: UUID = Field(..., description="Claim being scored")
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite credibility [0.0, 1.0]"
    )
    language_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Sensationalism detection [0.0, 1.0]; higher = more objective"
    )
    source_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Source credibility [0.0, 1.0]"
    )
    consistency_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Alignment with verified claims [0.0, 1.0]"
    )
    verifiability_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Falsifiability [0.0, 1.0]; opinions score lower"
    )
    reasoning: str = Field(
        ...,
        max_length=5000,
        description="Human-readable explanation of scores"
    )
    calculated_by: str = Field(
        ...,
        max_length=100,
        description="Algorithm version (e.g., 'nlp-v2.1', 'gpt4-classifier-v1.0')"
    )
    calculated_at: datetime = Field(..., description="When scoring was performed")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "claim_id": "550e8400-e29b-41d4-a716-446655440001",
                "overall_score": 0.15,
                "language_score": 0.2,
                "source_score": 0.75,
                "consistency_score": 0.1,
                "verifiability_score": 0.9,
                "reasoning": "High sensationalism detected. Source is credible but claim contradicts verified health sources.",
                "calculated_by": "nlp-v2.1",
                "calculated_at": "2024-01-15T10:30:00Z"
            }
        }


# ============================================================================
# CLAIM SCHEMAS
# ============================================================================

class ClaimCreate(BaseModel):
    """
    Claim creation request schema.
    
    Submitted by analysts to start fact-checking process.
    
    Attributes:
        content: The claim text (max 10,000 chars)
        source_id: UUID of information source
        source_url: Direct link to original claim
        category: Domain category for routing
    """
    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Claim text to verify",
        examples=["Vaccines contain microchips"]
    )
    source_id: UUID = Field(
        ...,
        description="UUID of information source"
    )
    source_url: Optional[str] = Field(
        None,
        max_length=2048,
        description="Direct URL to original claim",
        examples=["https://twitter.com/fake_account/123"]
    )
    category: ClaimCategory = Field(
        default=ClaimCategory.OTHER,
        description="Domain category (politics, health, finance, etc)"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "content": "COVID-19 vaccines contain microchips",
                "source_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_url": "https://twitter.com/misinformation/123",
                "category": "health"
            }
        }


class ClaimResponse(BaseModel):
    """
    Claim response schema (basic info).
    
    Returned by GET endpoints. Excludes full content for privacy.
    
    Attributes:
        id: UUID identifier
        content: Claim text
        category: Domain category
        source_id: Source ID
        is_processed: Whether credibility score exists
        created_at: Submission timestamp
        submitted_by: User ID who submitted
    """
    id: UUID = Field(..., description="Unique claim identifier")
    content: str = Field(..., description="Claim text")
    category: ClaimCategory = Field(..., description="Domain category")
    source_id: UUID = Field(..., description="Source identifier")
    is_processed: bool = Field(..., description="Whether score has been calculated")
    created_at: datetime = Field(..., description="Submission timestamp")
    submitted_by: UUID = Field(..., description="User ID who submitted claim")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "content": "COVID-19 vaccines contain microchips",
                "category": "health",
                "source_id": "550e8400-e29b-41d4-a716-446655440000",
                "is_processed": True,
                "created_at": "2024-01-15T10:30:00Z",
                "submitted_by": "550e8400-e29b-41d4-a716-446655440002"
            }
        }


class ClaimWithScoresResponse(ClaimResponse):
    """
    Claim response with credibility scores and related claims.
    
    Extended response including multi-dimensional scores and relationships.
    
    Attributes:
        credibility_score: Full credibility score breakdown (if scored)
        verifications_count: Number of human verifications
        consensus_verdict: Most common verification verdict
        related_claims: Related/contradicting claims
    """
    credibility_score: Optional[CredibilityScoreFull] = Field(
        None,
        description="Credibility score (null if not yet scored)"
    )
    verifications_count: int = Field(
        default=0,
        description="Number of human verifications"
    )
    consensus_verdict: Optional[VerificationVerdict] = Field(
        None,
        description="Most common verification verdict"
    )
    source: Optional[SourceResponse] = Field(
        None,
        description="Source information"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "content": "COVID-19 vaccines contain microchips",
                "category": "health",
                "source_id": "550e8400-e29b-41d4-a716-446655440000",
                "is_processed": True,
                "created_at": "2024-01-15T10:30:00Z",
                "submitted_by": "550e8400-e29b-41d4-a716-446655440002",
                "credibility_score": {
                    "overall_score": 0.15,
                    "language_score": 0.2
                },
                "verifications_count": 3,
                "consensus_verdict": "confirmed_false",
                "source": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Twitter",
                    "source_type": "social_media",
                    "credibility_score": 0.55
                }
            }
        }


class ClaimListResponse(BaseModel):
    """Paginated list of claims with scores"""
    total: int = Field(..., description="Total number of claims")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Pagination offset")
    items: List[ClaimWithScoresResponse] = Field(..., description="Claims in this page")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "total": 5000,
                "limit": 50,
                "offset": 0,
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "content": "COVID-19 vaccines contain microchips",
                        "category": "health",
                        "source_id": "550e8400-e29b-41d4-a716-446655440000",
                        "is_processed": True,
                        "created_at": "2024-01-15T10:30:00Z",
                        "submitted_by": "550e8400-e29b-41d4-a716-446655440002",
                        "credibility_score": {"overall_score": 0.15},
                        "verifications_count": 3,
                        "consensus_verdict": "confirmed_false"
                    }
                ]
            }
        }


# ============================================================================
# VERIFICATION SCHEMAS
# ============================================================================

class VerificationCreate(BaseModel):
    """
    Verification creation request schema.
    
    Submitted by verifiers to record fact-checking results.
    
    Attributes:
        claim_id: UUID of claim being verified
        verdict: Assessment outcome
        confidence_level: Verifier confidence [1-5]
        notes: Investigation details and evidence
    """
    claim_id: UUID = Field(..., description="Claim being verified")
    verdict: VerificationVerdict = Field(
        ...,
        description="Verification outcome"
    )
    confidence_level: int = Field(
        ...,
        ge=1,
        le=5,
        description="Confidence [1-5]; 1=minimal, 5=certain"
    )
    notes: Optional[str] = Field(
        None,
        max_length=5000,
        description="Investigation details and evidence sources"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "claim_id": "550e8400-e29b-41d4-a716-446655440001",
                "verdict": "confirmed_false",
                "confidence_level": 5,
                "notes": "Verified through CDC and WHO sources. No evidence of microchips in vaccines."
            }
        }


class VerificationResponse(BaseModel):
    """
    Verification response schema.
    
    Attributes:
        id: UUID identifier
        claim_id: Claim being verified
        verdict: Assessment outcome
        confidence_level: Verifier confidence [1-5]
        verified_by: User ID of verifier
        verified_at: When verification was completed
        verifier_username: Username of verifier (for display)
    """
    id: UUID = Field(..., description="Unique verification identifier")
    claim_id: UUID = Field(..., description="Claim being verified")
    verdict: VerificationVerdict = Field(..., description="Verification outcome")
    confidence_level: int = Field(..., description="Confidence [1-5]")
    verified_by: UUID = Field(..., description="User ID of verifier")
    verified_at: datetime = Field(..., description="When verification was completed")
    verifier_username: Optional[str] = Field(
        None,
        description="Username of verifier (for display)"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440010",
                "claim_id": "550e8400-e29b-41d4-a716-446655440001",
                "verdict": "confirmed_false",
                "confidence_level": 5,
                "verified_by": "550e8400-e29b-41d4-a716-446655440003",
                "verified_at": "2024-01-15T10:30:00Z",
                "verifier_username": "bob_verifier"
            }
        }


class VerificationListResponse(BaseModel):
    """List of verifications for a claim"""
    claim_id: UUID = Field(..., description="Claim ID")
    verifications: List[VerificationResponse] = Field(
        ...,
        description="All verifications for this claim"
    )
    consensus_verdict: Optional[VerificationVerdict] = Field(
        None,
        description="Most common verdict"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "claim_id": "550e8400-e29b-41d4-a716-446655440001",
                "verifications": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440010",
                        "claim_id": "550e8400-e29b-41d4-a716-446655440001",
                        "verdict": "confirmed_false",
                        "confidence_level": 5,
                        "verified_by": "550e8400-e29b-41d4-a716-446655440003",
                        "verified_at": "2024-01-15T10:30:00Z",
                        "verifier_username": "bob_verifier"
                    }
                ],
                "consensus_verdict": "confirmed_false"
            }
        }


# ============================================================================
# RELATED CLAIM SCHEMAS
# ============================================================================

class RelatedClaimResponse(BaseModel):
    """
    Related claim response schema.
    
    Represents relationship between two claims (contradiction, support, similar).
    
    Attributes:
        id: UUID identifier
        claim_1_id: Source claim (start of directed edge)
        claim_2_id: Target claim (end of directed edge)
        relationship_type: Type of relationship
        confidence: Algorithm confidence [0.0, 1.0]
        detected_at: When relationship was detected
    """
    id: UUID = Field(..., description="Unique relationship identifier")
    claim_1_id: UUID = Field(..., description="Source claim (start of edge)")
    claim_2_id: UUID = Field(..., description="Target claim (end of edge)")
    relationship_type: RelationshipType = Field(..., description="Relationship type")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Algorithm confidence in relationship [0.0, 1.0]"
    )
    detected_at: datetime = Field(..., description="When relationship was detected")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440020",
                "claim_1_id": "550e8400-e29b-41d4-a716-446655440001",
                "claim_2_id": "550e8400-e29b-41d4-a716-446655440002",
                "relationship_type": "contradicts",
                "confidence": 0.95,
                "detected_at": "2024-01-15T10:30:00Z"
            }
        }


class RelatedClaimsListResponse(BaseModel):
    """List of related claims"""
    claim_id: UUID = Field(..., description="Claim ID")
    relationship_type: Optional[RelationshipType] = Field(
        None,
        description="Filter by this relationship type"
    )
    related_claims: List[RelatedClaimResponse] = Field(
        ...,
        description="Related claims"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "claim_id": "550e8400-e29b-41d4-a716-446655440001",
                "relationship_type": "contradicts",
                "related_claims": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440020",
                        "claim_1_id": "550e8400-e29b-41d4-a716-446655440001",
                        "claim_2_id": "550e8400-e29b-41d4-a716-446655440002",
                        "relationship_type": "contradicts",
                        "confidence": 0.95,
                        "detected_at": "2024-01-15T10:30:00Z"
                    }
                ]
            }
        }


# ============================================================================
# AUDIT LOG SCHEMAS
# ============================================================================

class AuditLogResponse(BaseModel):
    """
    Audit log response schema.
    
    Immutable record of all platform actions for compliance/forensics.
    
    Attributes:
        id: UUID identifier
        user_id: User who performed action
        action: Type of action
        resource_type: Type of affected resource
        resource_id: ID of affected resource
        timestamp: When action occurred
        ip_address: Source IP (encrypted in production)
        user_agent: Client User-Agent string
        details: Additional context (JSON)
    """
    id: UUID = Field(..., description="Unique log entry identifier")
    user_id: UUID = Field(..., description="User who performed action")
    action: AuditAction = Field(..., description="Type of action")
    resource_type: str = Field(
        ...,
        description="Type of affected resource (claim, verification, user, etc)"
    )
    resource_id: Optional[UUID] = Field(
        None,
        description="ID of affected resource"
    )
    timestamp: datetime = Field(..., description="When action occurred")
    ip_address: Optional[str] = Field(
        None,
        description="Source IP address (encrypted in production)"
    )
    user_agent: Optional[str] = Field(
        None,
        description="HTTP User-Agent string"
    )
    details: Optional[dict] = Field(
        None,
        description="Additional context (JSON object)"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440030",
                "user_id": "550e8400-e29b-41d4-a716-446655440003",
                "action": "verified_claim",
                "resource_type": "verification",
                "resource_id": "550e8400-e29b-41d4-a716-446655440010",
                "timestamp": "2024-01-15T10:30:00Z",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0...",
                "details": {
                    "verdict": "confirmed_false",
                    "confidence": 5
                }
            }
        }


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries"""
    total: int = Field(..., description="Total number of entries")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Pagination offset")
    items: List[AuditLogResponse] = Field(..., description="Log entries in this page")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "total": 10000,
                "limit": 50,
                "offset": 0,
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440030",
                        "user_id": "550e8400-e29b-41d4-a716-446655440003",
                        "action": "verified_claim",
                        "resource_type": "verification",
                        "resource_id": "550e8400-e29b-41d4-a716-446655440010",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "ip_address": "192.168.1.100",
                        "user_agent": "Mozilla/5.0...",
                        "details": {"verdict": "confirmed_false", "confidence": 5}
                    }
                ]
            }
        }


# ============================================================================
# UTILITY SCHEMAS
# ============================================================================

class ErrorResponse(BaseModel):
    """Generic error response"""
    detail: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Source not found",
                "status_code": 404
            }
        }


class SuccessResponse(BaseModel):
    """Generic success response"""
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(None, description="Response data (varies by endpoint)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Claim created successfully",
                "data": {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "content": "Example claim"
                }
            }
        }


class PaginationParams(BaseModel):
    """
    Pagination parameters for list endpoints.
    
    Attributes:
        limit: Items per page (1-100, default 50)
        offset: Pagination offset (default 0)
    """
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Items per page"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Pagination offset"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "limit": 50,
                "offset": 0
            }
        }


# ============================================================================
# STATISTICS SCHEMAS
# ============================================================================

class ClaimStatsResponse(BaseModel):
    """Claim statistics by category"""
    category: ClaimCategory = Field(..., description="Claim category")
    total_claims: int = Field(..., description="Total claims in category")
    processed_claims: int = Field(..., description="Processed claims")
    pending_claims: int = Field(..., description="Unprocessed claims")
    confirmed_true: int = Field(..., description="Confirmed true verdicts")
    confirmed_false: int = Field(..., description="Confirmed false verdicts")
    misleading: int = Field(..., description="Misleading verdicts")
    
    class Config:
        json_schema_extra = {
            "example": {
                "category": "health",
                "total_claims": 500,
                "processed_claims": 450,
                "pending_claims": 50,
                "confirmed_true": 100,
                "confirmed_false": 300,
                "misleading": 50
            }
        }


class DashboardStatsResponse(BaseModel):
    """Overall dashboard statistics"""
    total_claims: int = Field(..., description="Total claims in system")
    processed_claims: int = Field(..., description="Claims with scores")
    pending_claims: int = Field(..., description="Unprocessed claims")
    total_verifications: int = Field(..., description="Total verification records")
    total_users: int = Field(..., description="Total platform users")
    processing_rate: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of claims processed"
    )
    stats_by_category: List[ClaimStatsResponse] = Field(
        ...,
        description="Statistics grouped by claim category"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_claims": 5000,
                "processed_claims": 4500,
                "pending_claims": 500,
                "total_verifications": 12000,
                "total_users": 150,
                "processing_rate": 90.0,
                "stats_by_category": [
                    {
                        "category": "health",
                        "total_claims": 2000,
                        "processed_claims": 1800,
                        "pending_claims": 200,
                        "confirmed_true": 400,
                        "confirmed_false": 1200,
                        "misleading": 200
                    }
                ]
            }
        }
