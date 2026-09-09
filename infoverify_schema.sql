-- ============================================================================
-- InfoVerify: Misinformation Detection Platform
-- PostgreSQL Schema (Production-Grade)
-- ============================================================================
-- This schema implements a comprehensive fact-checking and credibility scoring
-- system with audit logging, human verification workflows, and performance optimization.
-- ============================================================================

-- ============================================================================
-- EXTENSIONS & SETUP
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- ENUMS (Type definitions for categorical data)
-- ============================================================================

CREATE TYPE user_role AS ENUM ('viewer', 'analyst', 'verifier', 'admin');
COMMENT ON TYPE user_role IS 'Role hierarchy for access control: viewer (read-only), analyst (analysis), verifier (human verification), admin (platform control)';

CREATE TYPE source_type AS ENUM ('social_media', 'news', 'blog', 'forum', 'official', 'eyewitness');
COMMENT ON TYPE source_type IS 'Classification of information source types for weighted credibility assessment';

CREATE TYPE claim_category AS ENUM ('politics', 'health', 'finance', 'disaster', 'science', 'other');
COMMENT ON TYPE claim_category IS 'Categorical classification for claim type and domain-specific verification routing';

CREATE TYPE verification_verdict AS ENUM ('confirmed_true', 'confirmed_false', 'misleading', 'needs_more_info');
COMMENT ON TYPE verification_verdict IS 'Human verifier assessment of claim veracity after investigation';

CREATE TYPE relationship_type AS ENUM ('contradicts', 'supports', 'similar');
COMMENT ON TYPE relationship_type IS 'Type of relationship between related claims for contradiction detection';

CREATE TYPE audit_action AS ENUM (
  'verified_claim', 'submitted_claim', 'updated_score', 'created_source',
  'user_created', 'user_role_changed', 'source_activated', 'source_deactivated',
  'verification_deleted', 'claim_flagged', 'report_generated'
);
COMMENT ON TYPE audit_action IS 'Enumerated actions tracked in audit log for compliance and security monitoring';

-- ============================================================================
-- TABLE: users
-- ============================================================================
-- Core authentication and user management table with role-based access control.
-- SECURITY: email and password_hash should be encrypted at rest.
-- ============================================================================

CREATE TABLE users (
  -- Primary Key & Identity
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  
  -- Authentication (ENCRYPT: email, password_hash)
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  
  -- Profile
  username VARCHAR(100) UNIQUE NOT NULL,
  
  -- Access Control
  role user_role NOT NULL DEFAULT 'viewer'::user_role,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  
  -- Audit Timestamps
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMP WITH TIME ZONE,
  
  -- Constraints
  CONSTRAINT email_valid CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'),
  CONSTRAINT username_length CHECK (LENGTH(username) >= 3 AND LENGTH(username) <= 100),
  CONSTRAINT password_hash_not_empty CHECK (LENGTH(password_hash) > 0)
);

COMMENT ON TABLE users IS 'User authentication and access control. Email and password_hash should use pgcrypto encryption.';
COMMENT ON COLUMN users.id IS 'Unique identifier (UUID v4)';
COMMENT ON COLUMN users.email IS 'Email address for authentication (SHOULD BE ENCRYPTED)';
COMMENT ON COLUMN users.password_hash IS 'Bcrypt/Argon2 hash of password (consider encrypting column itself)';
COMMENT ON COLUMN users.username IS 'Display name for user profile';
COMMENT ON COLUMN users.role IS 'Role determining platform permissions and capabilities';
COMMENT ON COLUMN users.is_active IS 'Soft delete flag; inactive users cannot authenticate';
COMMENT ON COLUMN users.last_login_at IS 'Timestamp of most recent successful login for security audit';

-- Indexes for users
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- TABLE: sources
-- ============================================================================
-- Registry of information sources with baseline credibility scoring.
-- Sources act as data lineage for all claims in the system.
-- ============================================================================

CREATE TABLE sources (
  -- Primary Key
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  
  -- Identity
  name VARCHAR(255) NOT NULL UNIQUE,
  source_type source_type NOT NULL,
  
  -- Credibility Assessment
  credibility_score FLOAT NOT NULL DEFAULT 0.5,
  
  -- Metadata
  url VARCHAR(2048),
  description TEXT,
  
  -- Audit Timestamps
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Constraints
  CONSTRAINT credibility_score_valid CHECK (credibility_score >= 0.0 AND credibility_score <= 1.0),
  CONSTRAINT name_not_empty CHECK (LENGTH(name) > 0)
);

COMMENT ON TABLE sources IS 'Catalog of information sources (Twitter, NYT, Reddit, etc.) with inherent credibility scores for weighted verification.';
COMMENT ON COLUMN sources.id IS 'Unique identifier (UUID v4)';
COMMENT ON COLUMN sources.name IS 'Display name of source (e.g., "Twitter", "New York Times", "Reddit r/news")';
COMMENT ON COLUMN sources.source_type IS 'Classification affecting baseline credibility weight (social_media scores lower than official sources)';
COMMENT ON COLUMN sources.credibility_score IS 'Base credibility score [0.0, 1.0] learned from historical verification accuracy; updated periodically';
COMMENT ON COLUMN sources.url IS 'Homepage or primary URL of source for context and validation';
COMMENT ON COLUMN sources.description IS 'Human-readable description of source scope and focus';

-- Indexes for sources
CREATE INDEX idx_sources_source_type ON sources(source_type);
CREATE INDEX idx_sources_credibility_score ON sources(credibility_score DESC);
CREATE INDEX idx_sources_name ON sources(name);

-- ============================================================================
-- TABLE: claims
-- ============================================================================
-- Individual claims/statements submitted for verification against sources.
-- SECURITY: content should be encrypted to prevent disclosure of claims under investigation.
-- ============================================================================

CREATE TABLE claims (
  -- Primary Key
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  
  -- Content (ENCRYPT: content)
  content TEXT NOT NULL,
  
  -- Lineage
  source_id UUID NOT NULL,
  source_url VARCHAR(2048),
  submitted_by UUID NOT NULL,
  
  -- Classification
  category claim_category NOT NULL DEFAULT 'other'::claim_category,
  
  -- Processing Status
  is_processed BOOLEAN NOT NULL DEFAULT FALSE,
  processed_at TIMESTAMP WITH TIME ZONE,
  
  -- Audit Timestamps
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Constraints
  CONSTRAINT content_not_empty CHECK (LENGTH(content) > 0),
  CONSTRAINT content_max_length CHECK (LENGTH(content) <= 10000),
  CONSTRAINT source_id_not_null FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE RESTRICT,
  CONSTRAINT submitted_by_valid FOREIGN KEY (submitted_by) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT processed_at_logic CHECK (
    (is_processed = FALSE AND processed_at IS NULL) OR
    (is_processed = TRUE AND processed_at IS NOT NULL)
  )
);

COMMENT ON TABLE claims IS 'Individual claims submitted for fact-checking. Content should be encrypted at rest to maintain confidentiality of unverified claims.';
COMMENT ON COLUMN claims.id IS 'Unique identifier (UUID v4)';
COMMENT ON COLUMN claims.content IS 'The claim text to be verified (SHOULD BE ENCRYPTED); max 10,000 chars';
COMMENT ON COLUMN claims.source_id IS 'Foreign key linking to source where claim originated';
COMMENT ON COLUMN claims.source_url IS 'Direct URL/link to original claim for verifier reference';
COMMENT ON COLUMN claims.submitted_by IS 'User who submitted claim for verification (analyst or verifier)';
COMMENT ON COLUMN claims.category IS 'Domain category (politics, health, etc.) for routing and analysis';
COMMENT ON COLUMN claims.is_processed IS 'Whether credibility scoring algorithm has run on this claim';
COMMENT ON COLUMN claims.processed_at IS 'Timestamp when automated scoring was last executed';

-- Indexes for claims
CREATE INDEX idx_claims_source_id ON claims(source_id);
CREATE INDEX idx_claims_submitted_by ON claims(submitted_by);
CREATE INDEX idx_claims_category ON claims(category);
CREATE INDEX idx_claims_is_processed ON claims(is_processed) WHERE is_processed = FALSE;
CREATE INDEX idx_claims_created_at ON claims(created_at DESC);
CREATE INDEX idx_claims_created_at_category ON claims(created_at DESC, category);
-- Full-text search index for content (requires tsearch2)
CREATE INDEX idx_claims_content_tsvector ON claims USING gin(to_tsvector('english', content));

-- ============================================================================
-- TABLE: credibility_scores
-- ============================================================================
-- Detailed scoring breakdown for each claim across multiple dimensions.
-- Each score is calculated by an algorithm version and can be tracked over time.
-- ============================================================================

CREATE TABLE credibility_scores (
  -- Primary Key
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  
  -- Foreign Key
  claim_id UUID NOT NULL UNIQUE,
  
  -- Multi-Dimensional Scores [0.0, 1.0]
  overall_score FLOAT NOT NULL,
  language_score FLOAT NOT NULL,      -- sensationalism, emotional language detection
  source_score FLOAT NOT NULL,         -- credibility of originating source
  consistency_score FLOAT NOT NULL,    -- agreement with other verified claims
  verifiability_score FLOAT NOT NULL,  -- factual/falsifiable vs opinion
  
  -- Reasoning & Traceability
  reasoning TEXT NOT NULL,
  calculated_by VARCHAR(100) NOT NULL, -- algorithm version identifier (e.g., "v2.1.0", "gpt4-classifier")
  
  -- Audit Timestamps
  calculated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Constraints
  CONSTRAINT claim_id_valid FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE,
  CONSTRAINT overall_score_valid CHECK (overall_score >= 0.0 AND overall_score <= 1.0),
  CONSTRAINT language_score_valid CHECK (language_score >= 0.0 AND language_score <= 1.0),
  CONSTRAINT source_score_valid CHECK (source_score >= 0.0 AND source_score <= 1.0),
  CONSTRAINT consistency_score_valid CHECK (consistency_score >= 0.0 AND consistency_score <= 1.0),
  CONSTRAINT verifiability_score_valid CHECK (verifiability_score >= 0.0 AND verifiability_score <= 1.0),
  CONSTRAINT reasoning_not_empty CHECK (LENGTH(reasoning) > 0),
  CONSTRAINT calculated_by_not_empty CHECK (LENGTH(calculated_by) > 0)
);

COMMENT ON TABLE credibility_scores IS 'Multi-dimensional credibility assessment for each claim. Allows tracking score changes over time via calculated_at. One record per claim (UNIQUE constraint on claim_id).';
COMMENT ON COLUMN credibility_scores.id IS 'Unique identifier (UUID v4)';
COMMENT ON COLUMN credibility_scores.claim_id IS 'Foreign key to claims table; UNIQUE ensures one score per claim';
COMMENT ON COLUMN credibility_scores.overall_score IS 'Composite credibility [0.0, 1.0]; typically weighted average of sub-scores';
COMMENT ON COLUMN credibility_scores.language_score IS 'Linguistic analysis score: detects sensationalism, fear-mongering, loaded language; higher = more objective';
COMMENT ON COLUMN credibility_scores.source_score IS 'Source reliability score from sources.credibility_score; reflects outlet track record';
COMMENT ON COLUMN credibility_scores.consistency_score IS 'Alignment with verified claims; contradictions lower this score';
COMMENT ON COLUMN credibility_scores.verifiability_score IS 'Falsifiability assessment; opinions score lower, factual claims higher';
COMMENT ON COLUMN credibility_scores.reasoning IS 'Human-readable explanation of scoring logic (e.g., "Language detected fear-mongering (+0.1), source credibility 0.45 (-0.15), matches 3 verified claims (+0.25)")';
COMMENT ON COLUMN credibility_scores.calculated_by IS 'Algorithm identifier for reproducibility (e.g., "nlp-v2.1", "hybrid-gpt4-classifier-v1.0", "manual-verifier-consensus")';
COMMENT ON COLUMN credibility_scores.calculated_at IS 'When scoring was performed; allows tracking score evolution';

-- Indexes for credibility_scores
CREATE INDEX idx_credibility_scores_claim_id ON credibility_scores(claim_id);
CREATE INDEX idx_credibility_scores_overall_score ON credibility_scores(overall_score DESC);
CREATE INDEX idx_credibility_scores_calculated_at ON credibility_scores(calculated_at DESC);

-- ============================================================================
-- TABLE: verification_records
-- ============================================================================
-- Human verification verdicts by expert verifiers with confidence tracking.
-- SECURITY: notes should be encrypted as they may contain sensitive investigation details.
-- ============================================================================

CREATE TABLE verification_records (
  -- Primary Key
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  
  -- Foreign Keys
  claim_id UUID NOT NULL,
  verified_by UUID NOT NULL,
  
  -- Verdict
  verdict verification_verdict NOT NULL,
  confidence_level INTEGER NOT NULL,  -- 1-5 scale
  
  -- Investigation Details (ENCRYPT: notes)
  notes TEXT,
  
  -- Audit Timestamps
  verified_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Constraints
  CONSTRAINT claim_id_valid FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE,
  CONSTRAINT verified_by_valid FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT confidence_level_valid CHECK (confidence_level >= 1 AND confidence_level <= 5),
  CONSTRAINT notes_max_length CHECK (LENGTH(notes) <= 5000)
);

COMMENT ON TABLE verification_records IS 'Human verification verdicts from expert verifiers. Multiple verifications per claim allowed for consensus. Notes should be encrypted to protect investigation methodology.';
COMMENT ON COLUMN verification_records.id IS 'Unique identifier (UUID v4)';
COMMENT ON COLUMN verification_records.claim_id IS 'Foreign key to verified claim; allows multiple verifications per claim for consensus';
COMMENT ON COLUMN verification_records.verified_by IS 'User ID of verifier (must have verifier or admin role)';
COMMENT ON COLUMN verification_records.verdict IS 'Final assessment: confirmed_true, confirmed_false, misleading (partially true/misleading), or needs_more_info (insufficient evidence)';
COMMENT ON COLUMN verification_records.confidence_level IS 'Verifier confidence [1-5]; 1=minimal confidence, 5=complete certainty based on evidence';
COMMENT ON COLUMN verification_records.notes IS 'Sources checked, evidence found, reasoning for verdict (SHOULD BE ENCRYPTED); max 5,000 chars';
COMMENT ON COLUMN verification_records.verified_at IS 'When verification was completed';

-- Indexes for verification_records
CREATE INDEX idx_verification_records_claim_id ON verification_records(claim_id);
CREATE INDEX idx_verification_records_verified_by ON verification_records(verified_by);
CREATE INDEX idx_verification_records_verdict ON verification_records(verdict);
CREATE INDEX idx_verification_records_verified_at ON verification_records(verified_at DESC);
CREATE INDEX idx_verification_records_confidence ON verification_records(confidence_level DESC);
-- Query: "Find claims verified by user X with high confidence"
CREATE INDEX idx_verification_records_verifier_confidence ON verification_records(verified_by, confidence_level DESC);

-- ============================================================================
-- TABLE: related_claims
-- ============================================================================
-- Graph of relationships between claims for contradiction detection and coherence analysis.
-- Enables detection of claim contradictions and building evidence chains.
-- ============================================================================

CREATE TABLE related_claims (
  -- Primary Key
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  
  -- Foreign Keys (Directional: claim_1 -> relationship -> claim_2)
  claim_1_id UUID NOT NULL,
  claim_2_id UUID NOT NULL,
  
  -- Relationship
  relationship_type relationship_type NOT NULL,
  confidence FLOAT NOT NULL,  -- How sure we are of this relationship [0.0, 1.0]
  
  -- Audit Timestamps
  detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Constraints
  CONSTRAINT claim_1_id_valid FOREIGN KEY (claim_1_id) REFERENCES claims(id) ON DELETE CASCADE,
  CONSTRAINT claim_2_id_valid FOREIGN KEY (claim_2_id) REFERENCES claims(id) ON DELETE CASCADE,
  CONSTRAINT claims_different CHECK (claim_1_id != claim_2_id),
  CONSTRAINT confidence_valid CHECK (confidence >= 0.0 AND confidence <= 1.0),
  CONSTRAINT no_duplicate_relationships UNIQUE(claim_1_id, claim_2_id, relationship_type)
);

COMMENT ON TABLE related_claims IS 'Directed graph of claim relationships. Enables cascade detection: if claim A is false and contradicts claim B, B is less credible. Prevents redundant edges via UNIQUE constraint.';
COMMENT ON COLUMN related_claims.id IS 'Unique identifier (UUID v4)';
COMMENT ON COLUMN related_claims.claim_1_id IS 'Source claim (start of directed edge)';
COMMENT ON COLUMN related_claims.claim_2_id IS 'Target claim (end of directed edge)';
COMMENT ON COLUMN related_claims.relationship_type IS 'contradicts (A is false => B less credible), supports (A is true => B more credible), similar (same claim, different wording)';
COMMENT ON COLUMN related_claims.confidence IS 'Algorithm confidence in relationship [0.0, 1.0]; e.g., 0.95 = very confident these claims contradict';
COMMENT ON COLUMN related_claims.detected_at IS 'When relationship was algorithmically detected';

-- Indexes for related_claims
CREATE INDEX idx_related_claims_claim_1_id ON related_claims(claim_1_id);
CREATE INDEX idx_related_claims_claim_2_id ON related_claims(claim_2_id);
CREATE INDEX idx_related_claims_relationship_type ON related_claims(relationship_type);
CREATE INDEX idx_related_claims_confidence ON related_claims(confidence DESC);
-- Query: "Find all claims that contradict claim X with high confidence"
CREATE INDEX idx_related_claims_1_type_confidence ON related_claims(claim_1_id, relationship_type, confidence DESC);

-- ============================================================================
-- TABLE: audit_log
-- ============================================================================
-- Immutable compliance and security audit trail for regulatory requirements.
-- SECURITY: ip_address should be encrypted; consider encrypting entire row for PII protection.
-- ============================================================================

CREATE TABLE audit_log (
  -- Primary Key (No updates: append-only log)
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  
  -- Actor
  user_id UUID NOT NULL,
  
  -- Action Details
  action audit_action NOT NULL,
  resource_type VARCHAR(50) NOT NULL,  -- 'claim', 'verification', 'user', 'source', 'score'
  resource_id UUID,
  
  -- Context (ENCRYPT: ip_address, details)
  ip_address INET,
  user_agent VARCHAR(512),
  details JSONB,  -- Flexible schema for additional context
  
  -- Audit Timestamp (Immutable)
  timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Constraints
  CONSTRAINT user_id_valid FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT action_not_empty CHECK (LENGTH(resource_type) > 0)
);

COMMENT ON TABLE audit_log IS 'Immutable append-only audit trail for compliance, security, and forensics. IP address and detailed context (details JSONB) should be encrypted. No UPDATE or DELETE allowed on existing records.';
COMMENT ON COLUMN audit_log.id IS 'Unique identifier (UUID v4)';
COMMENT ON COLUMN audit_log.user_id IS 'User who performed the action';
COMMENT ON COLUMN audit_log.action IS 'Type of action performed (verified_claim, submitted_claim, etc.)';
COMMENT ON COLUMN audit_log.resource_type IS 'Type of resource affected (claim, verification, user, score, source)';
COMMENT ON COLUMN audit_log.resource_id IS 'ID of affected resource; nullable for some actions (e.g., user_created might not reference a claim)';
COMMENT ON COLUMN audit_log.ip_address IS 'Source IP address of action (SHOULD BE ENCRYPTED for PII protection)';
COMMENT ON COLUMN audit_log.user_agent IS 'HTTP User-Agent string for device/client tracking';
COMMENT ON COLUMN audit_log.details IS 'JSON object with flexible schema for action-specific context (SHOULD BE ENCRYPTED); e.g., {"previous_score": 0.45, "new_score": 0.62, "reason": "human_verification"}';
COMMENT ON COLUMN audit_log.timestamp IS 'When action occurred; indexed for range queries and compliance reporting';

-- Indexes for audit_log
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_resource_id ON audit_log(resource_id);
-- Query: "Audit all actions on claim X"
CREATE INDEX idx_audit_log_resource_type_id ON audit_log(resource_type, resource_id);
-- Query: "All verifications on date X"
CREATE INDEX idx_audit_log_action_timestamp ON audit_log(action, timestamp DESC);

-- ============================================================================
-- GRANT PERMISSIONS (RBAC Setup)
-- ============================================================================
-- Example RBAC configuration (adjust roles and schema as needed)
-- NOTE: Create database roles first:
--   CREATE ROLE infoverify_viewer;
--   CREATE ROLE infoverify_analyst;
--   CREATE ROLE infoverify_verifier;
--   CREATE ROLE infoverify_admin;

-- All users can read sources
-- GRANT SELECT ON TABLE sources TO infoverify_viewer;
-- GRANT SELECT ON TABLE sources TO infoverify_analyst;
-- GRANT SELECT ON TABLE sources TO infoverify_verifier;

-- Analysts can submit and view claims
-- GRANT SELECT, INSERT ON TABLE claims TO infoverify_analyst;
-- GRANT SELECT ON TABLE credibility_scores TO infoverify_analyst;

-- Verifiers can view scores and create verification records
-- GRANT SELECT ON TABLE claims TO infoverify_verifier;
-- GRANT SELECT ON TABLE credibility_scores TO infoverify_verifier;
-- GRANT SELECT, INSERT ON TABLE verification_records TO infoverify_verifier;

-- Only admins can manage users and audit
-- GRANT ALL ON TABLE users TO infoverify_admin;
-- GRANT ALL ON TABLE audit_log TO infoverify_admin;

-- ============================================================================
-- COMMENTS: ENCRYPTION RECOMMENDATIONS
-- ============================================================================
-- Implement field-level encryption using pgcrypto or transparent data encryption:
--
-- HIGH PRIORITY (Direct user data):
--   - users.email → pgcrypto.pgp_sym_encrypt()
--   - users.password_hash → Consider encrypting (already salted/hashed)
--   - claims.content → pgcrypto.pgp_sym_encrypt()
--   - verification_records.notes → pgcrypto.pgp_sym_encrypt()
--   - audit_log.ip_address → pgcrypto.pgp_sym_encrypt() or hash
--   - audit_log.details → pgcrypto.pgp_sym_encrypt()
--
-- MEDIUM PRIORITY (Derived data):
--   - sources.url → Consider encrypting if sensitive
--   - claims.source_url → Consider encrypting
--
-- Decryption in application layer; store encryption key in secure KMS (AWS KMS, HashiCorp Vault).
--
-- ============================================================================

-- ============================================================================
-- SCHEMA VERSION & CHANGELOG
-- ============================================================================
-- v1.0.0 - Initial schema with 7 core tables
--   - Users with RBAC
--   - Sources registry with credibility scoring
--   - Claims submission and processing
--   - Multi-dimensional credibility scoring
--   - Human verification with consensus support
--   - Claim relationship graph for contradiction detection
--   - Immutable audit log for compliance
--   - Comprehensive indexing for query performance
--   - Field-level encryption recommendations documented
-- ============================================================================
