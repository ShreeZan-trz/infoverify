"""
Credibility Scoring Engine
Analyzes claims across 5 dimensions to determine credibility
"""

from nltk.sentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
import nltk
import re

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
# SCORING FUNCTION 1: LANGUAGE SENSATIONALISM
# ============================================================================

def score_language_sensationalism(claim: str) -> float:
    """
    Detects sensational language (ALL CAPS, exclamation marks, emotional words)
    
    Returns: 0-1 score
    - 0.0 = calm, factual language
    - 1.0 = very sensational
    """
    
    if not claim:
        return 0.5
    
    score = 0.0
    
    # Check for ALL CAPS (more than 30% uppercase = sensational)
    uppercase_ratio = sum(1 for c in claim if c.isupper()) / len(claim)
    if uppercase_ratio > 0.3:
        score += 0.3
    
    # Check for exclamation marks (each one adds points)
    exclamation_count = claim.count('!')
    if exclamation_count > 0:
        score += min(0.2, exclamation_count * 0.1)  # Max 0.2 points
    
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
    
    # Cap at 1.0
    return min(score, 1.0)


# ============================================================================
# SCORING FUNCTION 2: SOURCE REPUTATION
# ============================================================================

def score_source_reputation(source: str) -> float:
    """
    Looks up source credibility from database
    
    Returns: 0-1 score based on source reliability
    - 0.0 = completely untrustworthy
    - 1.0 = extremely trustworthy (WHO, Reuters, etc.)
    """
    
    if not source:
        return 0.5
    
    source_lower = source.lower().strip()
    
    # Exact match
    if source_lower in SOURCE_CREDIBILITY:
        return SOURCE_CREDIBILITY[source_lower]
    
    # Partial match (if source contains a known source)
    for known_source, score in SOURCE_CREDIBILITY.items():
        if known_source in source_lower:
            return score
    
    # Default if unknown
    return 0.5


# ============================================================================
# SCORING FUNCTION 3: CONSISTENCY WITH OFFICIAL DATA
# ============================================================================

def score_consistency(claim: str) -> float:
    """
    Checks if claim matches official verified data
    
    For demo: We check against known official claims
    In production: Would query a database of verified claims
    
    Returns: 0-1 score
    - 0.0 = completely contradicts official data
    - 1.0 = perfectly matches official data
    """
    
    if not claim:
        return 0.5
    
    claim_lower = claim.lower()
    
    # Example: Nepal floods 2026
    # Official data says ~347 deaths in Rasuwa
    
    # If claim says 5000+ deaths, it's inconsistent
    if any(num in claim for num in ['5000', '5,000', 'thousands', '10000', '10,000']):
        if 'rasuwa' in claim_lower or 'district' in claim_lower:
            return 0.15  # Inconsistent with official count
    
    # If claim matches official numbers, it's consistent
    if '347' in claim or '300' in claim or 'official' in claim_lower:
        return 0.85
    
    # Neutral: we don't know, so middle score
    return 0.5


# ============================================================================
# SCORING FUNCTION 4: VERIFIABILITY
# ============================================================================

def score_verifiability(claim: str) -> float:
    """
    Checks if claim is specific enough to verify
    
    Looks for:
    - Named locations
    - Specific numbers
    - Dates
    - Named groups/people
    
    Returns: 0-1 score
    - 0.0 = too vague to verify
    - 1.0 = very specific, easily verifiable
    """
    
    if not claim:
        return 0.3
    
    score = 0.0
    
    # Check for numbers (specific claims have numbers)
    if re.search(r'\d+', claim):
        score += 0.3
    
    # Check for location names (common Nepal locations)
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
    
    # Cap at 1.0
    return min(score, 1.0)


# ============================================================================
# SCORING FUNCTION 5: SENTIMENT (FEAR-MONGERING)
# ============================================================================

def score_sentiment(claim: str) -> float:
    """
    Detects fear-mongering language
    
    Uses sentiment analysis to find negative emotional language
    
    Returns: 0-1 score
    - 0.0 = neutral/positive sentiment (not fear-mongering)
    - 1.0 = very negative/fear-mongering
    """
    
    if not claim:
        return 0.5
    
    # Use VADER sentiment analyzer
    sentiment = sia.polarity_scores(claim)
    
    # compound score: -1 (very negative) to +1 (very positive)
    compound = sentiment['compound']
    
    # Convert to 0-1 scale (flip so negative = high score)
    # -1 → 1.0, -0.5 → 0.75, 0 → 0.5, +0.5 → 0.25, +1 → 0.0
    fear_score = (1 - compound) / 2
    
    return fear_score


# ============================================================================
# FINAL SCORE CALCULATION
# ============================================================================

def calculate_credibility_score(claim: str, source: str) -> dict:
    """
    Calculate overall credibility score from 5 dimensions
    
    Returns: Dictionary with all scores and recommendation
    """
    
    # Calculate individual scores
    language_score = score_language_sensationalism(claim)
    source_score = score_source_reputation(source)
    consistency_score = score_consistency(claim)
    verifiability_score = score_verifiability(claim)
    sentiment_score = score_sentiment(claim)
    
    # Calculate overall (average of all 5)
    overall_score = (
        language_score +
        source_score +
        consistency_score +
        verifiability_score +
        sentiment_score
    ) / 5
    
    # Determine recommendation based on overall score
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