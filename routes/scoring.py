"""
Credibility Scoring Routes
API endpoints for analyzing claim credibility
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from nltk.sentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
import nltk
import re

from database import get_db
from models import Claim, CredibilityScore

# Download required NLTK data (run once)
try:
    nltk.data.find('vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon')

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()

# Source credibility database
SOURCE_CREDIBILITY = {
    "reuters": 0.90,
    "bbc": 0.88,
    "who": 0.95,
    "government": 0.85,
    "official": 0.85,
    "press": 0.80,
    "news": 0.75,
    "local news": 0.70,
    "eyewitness": 0.60,
    "blog": 0.40,
    "facebook": 0.30,
    "twitter": 0.25,
    "social media": 0.20,
    "unknown": 0.50,
}

# ============================================================================
# SCORING FUNCTIONS
# ============================================================================

def score_language_sensationalism(claim: str) -> float:
    """Detects sensational language (ALL CAPS, exclamation marks, emotional words)"""
    if not claim:
        return 0.5
    
    score = 0.0
    
    # Check for ALL CAPS
    uppercase_ratio = sum(1 for c in claim if c.isupper()) / len(claim)
    if uppercase_ratio > 0.3:
        score += 0.3
    
    # Check for exclamation marks
    exclamation_count = claim.count('!')
    if exclamation_count > 0:
        score += min(0.2, exclamation_count * 0.1)
    
    # Check for emotional words
    emotional_words = [
        'horrify', 'shocking', 'disaster', 'catastrophe', 'devastating',
        'tragedy', 'terrible', 'awful', 'horrible', 'massive', 'huge',
        'unbelievable', 'incredible', 'astonishing', 'emergency'
    ]
    
    claim_lower = claim.lower()
    for word in emotional_words:
        if word in claim_lower:
            score += 0.1
    
    return min(score, 1.0)


def score_source_reputation(source: str) -> float:
    """Looks up source credibility from database"""
    if not source:
        return 0.5
    
    source_lower = source.lower().strip()
    
    # Exact match
    if source_lower in SOURCE_CREDIBILITY:
        return SOURCE_CREDIBILITY[source_lower]
    
    # Partial match
    for known_source, score in SOURCE_CREDIBILITY.items():
        if known_source in source_lower:
            return score
    
    # Default if unknown
    return 0.5


def score_consistency(claim: str) -> float:
    """Checks if claim matches official verified data"""
    if not claim:
        return 0.5
    
    claim_lower = claim.lower()
    
    # If claim says 5000+ deaths in Rasuwa, it's inconsistent
    if any(num in claim for num in ['5000', '5,000', 'thousands', '10000', '10,000']):
        if 'rasuwa' in claim_lower or 'district' in claim_lower:
            return 0.15
    
    # If claim matches official numbers
    if '347' in claim or '300' in claim or 'official' in claim_lower:
        return 0.85
    
    # Neutral
    return 0.5


def score_verifiability(claim: str) -> float:
    """Checks if claim is specific enough to verify"""
    if not claim:
        return 0.3
    
    score = 0.0
    
    # Check for numbers
    if re.search(r'\d+', claim):
        score += 0.3
    
    # Check for location names
    locations = ['kathmandu', 'rasuwa', 'nuwakot', 'dhading', 'bhaktapur', 
                 'district', 'region', 'area', 'city', 'town']
    if any(location in claim.lower() for location in locations):
        score += 0.3
    
    # Check for dates
    if re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|january|february|march|april|may|june|july|august|september|october|november|december', claim.lower()):
        score += 0.2
    
    # Check for named groups
    if any(group in claim.lower() for group in ['people', 'families', 'victims', 'deaths', 'injured', 'affected']):
        score += 0.2
    
    return min(score, 1.0)


def score_sentiment(claim: str) -> float:
    """Detects fear-mongering language"""
    if not claim:
        return 0.5
    
    # Use VADER sentiment analyzer
    sentiment = sia.polarity_scores(claim)
    compound = sentiment['compound']
    
    # Convert to 0-1 scale
    fear_score = (1 - compound) / 2
    
    return fear_score


def calculate_credibility_score(claim: str, source: str) -> dict:
    """Calculate overall credibility score from 5 dimensions"""
    
    # Calculate individual scores
    language_score = score_language_sensationalism(claim)
    source_score = score_source_reputation(source)
    consistency_score = score_consistency(claim)
    verifiability_score = score_verifiability(claim)
    sentiment_score = score_sentiment(claim)
    
    # Calculate overall
    overall_score = (
        language_score +
        source_score +
        consistency_score +
        verifiability_score +
        sentiment_score
    ) / 5
    
    # Determine verdict
    if overall_score >= 0.7:
        verdict = "LIKELY TRUE"
        emoji = "✓"
    elif overall_score >= 0.5:
        verdict = "UNCERTAIN"
        emoji = "⚠"
    else:
        verdict = "LIKELY FALSE"
        emoji = "✗"
    
    # Build reasoning
    reasoning = []
    if source_score < 0.5:
        reasoning.append(f"Source ({source}) is not very credible")
    if language_score > 0.6:
        reasoning.append("Language is sensational")
    if consistency_score < 0.3:
        reasoning.append("Contradicts official reports")
    if verifiability_score < 0.4:
        reasoning.append("Claim is too vague to verify")
    if sentiment_score > 0.6:
        reasoning.append("Contains fear-mongering language")
    
    if not reasoning:
        reasoning.append("Claim appears reasonable")
    
    return {
        "overall_score": round(overall_score, 2),
        "language_score": round(language_score, 2),
        "source_score": round(source_score, 2),
        "consistency_score": round(consistency_score, 2),
        "verifiability_score": round(verifiability_score, 2),
        "sentiment_score": round(sentiment_score, 2),
        "verdict": verdict,
        "emoji": emoji,
        "reasoning": reasoning
    }

# ============================================================================
# ROUTE SETUP
# ============================================================================

router = APIRouter(prefix="/api", tags=["scoring"])

# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class ScoreClaimRequest(BaseModel):
    """Schema for scoring a claim"""
    claim_text: str
    source: str


class ScoreClaimResponse(BaseModel):
    """Schema for scoring response"""
    overall_score: float
    language_score: float
    source_score: float
    consistency_score: float
    verifiability_score: float
    sentiment_score: float
    verdict: str
    emoji: str
    reasoning: list


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/score-claim", response_model=ScoreClaimResponse)
def score_claim(request: ScoreClaimRequest, db: Session = Depends(get_db)):
    """
    Analyze a claim's credibility
    
    Takes a claim and source, analyzes across 5 dimensions
    Returns: Credibility score (0-1) and reasoning
    """
    
    # Validate input
    if not request.claim_text or len(request.claim_text.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Claim text cannot be empty"
        )
    
    if not request.source or len(request.source.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source cannot be empty"
        )
    
    # Calculate credibility score
    result = calculate_credibility_score(request.claim_text, request.source)
    
    return result


@router.post("/analyze-and-save")
def analyze_and_save_claim(
    claim_id: str,
    source: str,
    db: Session = Depends(get_db)
):
    """Analyze a claim and save score to database"""
    
    # Find the claim
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found"
        )
    
    # Calculate score
    result = calculate_credibility_score(claim.content, source)
    
    # Save to database
    credibility_score = CredibilityScore(
        claim_id=claim.id,
        overall_score=result['overall_score'],
        language_score=result['language_score'],
        source_score=result['source_score'],
        consistency_score=result['consistency_score'],
        verifiability_score=result['verifiability_score'],
        reasoning="\n".join(result['reasoning']),
        calculated_by="AI"
    )
    
    db.add(credibility_score)
    db.commit()
    db.refresh(credibility_score)
    
    return {
        "message": "Claim analyzed and saved",
        "claim_id": str(claim.id),
        "score": result['overall_score'],
        "verdict": result['verdict']
    }