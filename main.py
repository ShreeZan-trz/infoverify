"""
InfoVerify - Main Application Entry Point
==========================================
FastAPI application for misinformation detection and fact-checking.

Configuration:
    - Database: PostgreSQL with SQLAlchemy ORM
    - API: FastAPI with OpenAPI documentation
    - Logging: Structured logging for debugging
    - CORS: Enabled for development (disable in production)

Routes:
    - GET  / - Root endpoint
    - GET  /health - Health check
    - POST /api/claims - Submit claim
    - GET  /api/claims - List claims
    - GET  /api/claims/{id} - Get claim details
    - PATCH /api/claims/{id}/verify - Verify claim
    - GET  /api/sources - List sources
    - POST /api/sources - Create source

Usage:
    # Development
    python main.py
    
    # Production with gunicorn
    gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
"""

import os
import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

# Database imports
from database import Base, engine, get_db

# Routes imports
from routes.claims import router as claims_router


# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_db():
    """
    Initialize database tables on application startup.
    
    Creates all tables defined in SQLAlchemy models if they don't exist.
    This is idempotent - safe to call multiple times.
    
    Note: In production, use Alembic for database migrations instead.
    """
    try:
        logger.info("Initializing database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="InfoVerify API",
    description="Misinformation Detection and Fact-Checking Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# ============================================================================
# MIDDLEWARE SETUP
# ============================================================================

@app.middleware("http")
async def add_request_id(request, call_next):
    """
    Add request ID to response headers for tracing.
    
    Useful for debugging and correlating logs across services.
    
    Args:
        request: HTTP request
        call_next: Next middleware/route handler
        
    Returns:
        Response with X-Request-ID header
    """
    request.state.request_id = datetime.utcnow().isoformat()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


# Add CORS middleware
# TODO: In production, set allow_origins to specific domain(s)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Development: allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Initialize application on startup.
    
    This event runs once when the FastAPI application starts.
    Used to set up resources like database connections, caches, etc.
    """
    logger.info("=" * 80)
    logger.info("InfoVerify API Starting Up")
    logger.info("=" * 80)
    
    try:
        # Initialize database
        init_db()
        
        # Log startup info
        logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
        logger.info(f"API Version: 1.0.0")
        logger.info(f"Documentation: http://localhost:8000/docs")
        
        logger.info("Application startup completed successfully")
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on application shutdown.
    
    This event runs when the FastAPI application shuts down.
    Used to close connections, clean up resources, etc.
    """
    logger.info("=" * 80)
    logger.info("InfoVerify API Shutting Down")
    logger.info("=" * 80)
    
    try:
        logger.info("Closing database connections...")
        # Add cleanup code here if needed
        logger.info("Shutdown completed successfully")
    except Exception as e:
        logger.error(f"Shutdown error: {e}", exc_info=True)


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get(
    "/",
    tags=["system"],
    responses={200: {"description": "API is running"}}
)
async def root():
    """
    Root endpoint.
    
    Returns basic API information and documentation links.
    
    Returns:
        dict: API info with documentation links
    """
    return {
        "name": "InfoVerify API",
        "description": "Misinformation Detection and Fact-Checking Platform",
        "version": "1.0.0",
        "status": "running",
        "documentation": {
            "swagger": "http://localhost:8000/docs",
            "redoc": "http://localhost:8000/redoc",
            "openapi": "http://localhost:8000/openapi.json"
        },
        "endpoints": {
            "claims": "/api/claims",
            "sources": "/api/sources",
            "health": "/health"
        }
    }


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.get(
    "/health",
    tags=["system"],
    responses={200: {"description": "Service is healthy"}}
)
async def health_check():
    """
    Health check endpoint.
    
    Returns the current health status of the API including database connectivity.
    Used by load balancers and monitoring systems.
    
    Returns:
        dict: Health status, timestamp, and service info
    """
    try:
        # Check database connection
        db = next(get_db())
        # Simple query to verify database is responding
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
        db_error = None
    except Exception as e:
        db_status = "disconnected"
        db_error = str(e)
        logger.warning(f"Database health check failed: {e}")
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "infoverify-api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "database": {
            "status": db_status,
            "error": db_error
        }
    }


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """
    Custom HTTP exception handler.
    
    Returns consistent error response format for all HTTP errors.
    
    Args:
        request: HTTP request
        exc: HTTPException raised
        
    Returns:
        JSONResponse with error details
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """
    Generic exception handler for unexpected errors.
    
    Logs the error and returns a generic 500 response without leaking details.
    
    Args:
        request: HTTP request
        exc: Exception raised
        
    Returns:
        JSONResponse with generic error message
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

# Include claims and sources routes
app.include_router(
    claims_router,
    prefix="/api",
    tags=["claims", "sources"]
)


# ============================================================================
# APPLICATION FACTORY
# ============================================================================

def create_app():
    """
    Application factory function.
    
    Can be used for testing or creating multiple app instances.
    
    Returns:
        FastAPI: Configured FastAPI application
    """
    return app


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Configuration from environment variables
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    environment = os.getenv("ENVIRONMENT", "development")
    
    # Uvicorn configuration
    config = {
        "app": "main:app",
        "host": host,
        "port": port,
        "reload": environment == "development",
        "log_level": "info" if environment == "production" else "debug"
    }
    
    logger.info(f"Starting server with config: {config}")
    uvicorn.run(**config)
