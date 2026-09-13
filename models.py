"""
InfoVerify SQLAlchemy ORM Models
Database models for misinformation detection platform
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column, String, Text, Float, Boolean, DateTime, Integer, ForeignKey,
    Enum as SQLEnum, Index, CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, INET
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# Helper function to ensure SQLAlchemy writes Enum values ('viewer') not names ('VIEWER')
def enum_values(enum_cls):
    return [e.value for e in enum_cls]

# ============================================================================
# ENUMS
# ============================================================================

class UserRole(str, Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    VERIFIER = "verifier"
    ADMIN = "admin"

class SourceType(str, Enum):
    SOCIAL_MEDIA = "social_media"
    NEWS = "news"
    BLOG = "blog"
    FORUM = "forum"
    OFFICIAL = "official"
    EYEWITNESS = "eyewitness"

class ClaimCategory(str, Enum):
    POLITICS = "politics"
    HEALTH = "health"
    FINANCE = "finance"
    DISASTER = "disaster"
    SCIENCE = "science"
    OTHER = "other"

class VerificationVerdict(str, Enum):
    CONFIRMED_TRUE = "confirmed_true"
    CONFIRMED_FALSE = "confirmed_false"
    MISLEADING = "misleading"
    NEEDS_MORE_INFO = "needs_more_info"

class RelationshipType(str, Enum):
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    SIMILAR = "similar"

class AuditAction(str, Enum):
    VERIFIED_CLAIM = "verified_claim"
    SUBMITTED_CLAIM = "submitted_claim"
    UPDATED_SCORE = "updated_score"
    CREATED_SOURCE = "created_source"
    UPDATED_USER = "updated_user"
    DELETED_CLAIM = "deleted_claim"

# ============================================================================
# MODELS
# ============================================================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        SQLEnum(UserRole, name="user_role", values_callable=enum_values),
        default=UserRole.VIEWER,
        nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    claims = relationship("Claim", back_populates="submitted_by_user", foreign_keys="Claim.submitted_by")
    verifications = relationship("VerificationRecord", back_populates="verifier_user")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class Source(Base):
    __tablename__ = "sources"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    source_type = Column(
        SQLEnum(SourceType, name="source_type", values_callable=enum_values),
        nullable=False
    )
    credibility_score = Column(Float, default=0.5, nullable=False)
    url = Column(String(500))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    claims = relationship("Claim", back_populates="source")
    
    def __repr__(self):
        return f"<Source(id={self.id}, name={self.name}, credibility={self.credibility_score})>"


class Claim(Base):
    __tablename__ = "claims"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    source_id = Column(PG_UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False, index=True)
    source_url = Column(String(500))
    submitted_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    category = Column(
        SQLEnum(ClaimCategory, name="claim_category", values_callable=enum_values),
        default=ClaimCategory.OTHER,
        nullable=False
    )
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    source = relationship("Source", back_populates="claims")
    submitted_by_user = relationship("User", back_populates="claims", foreign_keys=[submitted_by])
    credibility_score = relationship("CredibilityScore", uselist=False, back_populates="claim", cascade="all, delete-orphan")
    verifications = relationship("VerificationRecord", back_populates="claim", cascade="all, delete-orphan")
    related_claims = relationship("RelatedClaim", foreign_keys="RelatedClaim.claim_1_id", back_populates="claim_1")
    
    __table_args__ = (
        Index("idx_claim_category", "category"),
        Index("idx_claim_created", "created_at"),
    )
    
    def __repr__(self):
        return f"<Claim(id={self.id}, category={self.category})>"


class CredibilityScore(Base):
    __tablename__ = "credibility_scores"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(PG_UUID(as_uuid=True), ForeignKey("claims.id"), unique=True, nullable=False, index=True)
    overall_score = Column(Float, nullable=False)
    language_score = Column(Float)
    source_score = Column(Float)
    consistency_score = Column(Float)
    verifiability_score = Column(Float)
    reasoning = Column(Text)
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    calculated_by = Column(String(100))
    
    # Relationships
    claim = relationship("Claim", back_populates="credibility_score")
    
    __table_args__ = (
        CheckConstraint("overall_score >= 0 AND overall_score <= 1"),
        Index("idx_credibility_score", "overall_score"),
    )
    
    def __repr__(self):
        return f"<CredibilityScore(id={self.id}, score={self.overall_score})>"


class VerificationRecord(Base):
    __tablename__ = "verification_records"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(PG_UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False, index=True)
    verified_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    verdict = Column(
        SQLEnum(VerificationVerdict, name="verification_verdict", values_callable=enum_values),
        nullable=False
    )
    confidence_level = Column(Integer, default=3)
    notes = Column(Text)
    verified_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    claim = relationship("Claim", back_populates="verifications")
    verifier_user = relationship("User", back_populates="verifications", foreign_keys=[verified_by])
    
    __table_args__ = (
        CheckConstraint("confidence_level >= 1 AND confidence_level <= 5"),
        Index("idx_verification_verdict", "verdict"),
    )
    
    def __repr__(self):
        return f"<VerificationRecord(id={self.id}, verdict={self.verdict})>"


class RelatedClaim(Base):
    __tablename__ = "related_claims"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_1_id = Column(PG_UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False, index=True)
    claim_2_id = Column(PG_UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False, index=True)
    relationship_type = Column(
        SQLEnum(RelationshipType, name="relationship_type", values_callable=enum_values),
        nullable=False
    )
    confidence = Column(Float, default=0.5)
    
    # Relationships
    claim_1 = relationship("Claim", foreign_keys=[claim_1_id], back_populates="related_claims")
    
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1"),
        Index("idx_related_claims_type", "relationship_type"),
    )
    
    def __repr__(self):
        return f"<RelatedClaim(id={self.id}, type={self.relationship_type})>"


class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    action = Column(
        SQLEnum(AuditAction, name="audit_action", values_callable=enum_values),
        nullable=False,
        index=True
    )
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(PG_UUID(as_uuid=True), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    details = Column(JSONB, default=dict)
    ip_address = Column(INET)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, timestamp={self.timestamp})>"