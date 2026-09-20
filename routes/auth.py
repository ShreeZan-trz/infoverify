"""
Authentication routes for InfoVerify
Handles user registration, login, and token management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import timedelta

from database import get_db
from models import User, UserRole
from security import (
    hash_password, 
    verify_password, 
    create_access_token,
    create_refresh_token,
    validate_password_strength
)

# ============================================================================
# ROUTE SETUP
# ============================================================================

router = APIRouter(tags=["authentication"])

# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class UserRegister(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    username: str
    password: str


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str
    refresh_token: str
    token_type: str
    user_id: str
    email: str
    role: str


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh"""
    refresh_token: str


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/register", response_model=dict)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    Returns: User info and tokens
    """
    
    # 1. Validate password strength
    is_valid, message = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # 2. Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 3. Check if username already exists
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # 4. Hash password
    hashed_password = hash_password(user_data.password)
    
    # 5. Create new user with explicit role
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=hashed_password,
        role=UserRole.VIEWER
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 6. Generate tokens
    access_token = create_access_token(
        data={"sub": str(new_user.id), "role": new_user.role.value}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(new_user.id)}
    )
    
    return {
        "message": "User registered successfully",
        "user_id": str(new_user.id),
        "email": new_user.email,
        "username": new_user.username,
        "role": new_user.role.value,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    Returns: Access token, refresh token, and user info
    """
    
    # 1. Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # 2. Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # 3. Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # 4. Generate tokens
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id)}
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user_id=str(user.id),
        email=user.email,
        role=user.role.value
    )


@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token.
    """
    from security import get_user_from_token
    
    try:
        # 1. Validate refresh token
        user_info = get_user_from_token(request.refresh_token)
        user_id = user_info["user_id"]
        
        # 2. Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # 3. Generate new access token
        new_access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role.value}
        )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout")
def logout():
    """
    Logout endpoint.
    
    Client just deletes token from local storage.
    """
    return {
        "message": "Logged out successfully"
    }