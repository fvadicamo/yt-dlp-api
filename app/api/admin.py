"""Admin API endpoints."""

from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status  # type: ignore[import-not-found]
from pydantic import BaseModel

from app.providers.exceptions import CookieError
from app.services.cookie_service import CookieService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class CookieValidationResponse(BaseModel):
    """Response for cookie validation."""

    provider: str
    is_valid: bool
    age_hours: Optional[float] = None
    warning: Optional[str] = None


class CookieReloadResponse(BaseModel):
    """Response for cookie reload."""

    success: bool
    provider: str
    message: str
    age_hours: Optional[float] = None


# Dependency to get cookie service (will be implemented in main app)
async def get_cookie_service() -> CookieService:
    """Get cookie service instance."""
    # This will be overridden by dependency injection in main app
    raise NotImplementedError("Cookie service dependency not configured")


@router.post("/validate-cookie", response_model=CookieValidationResponse)
async def validate_cookie(
    provider: str,
    cookie_service: CookieService = Depends(get_cookie_service),  # noqa: B008
) -> Any:
    """
    Validate cookie for a provider.

    This endpoint tests cookie validity including authentication.

    Args:
        provider: Provider name (e.g., "youtube")
        cookie_service: Cookie service instance

    Returns:
        Validation result with cookie status

    Raises:
        HTTPException: If validation fails
    """
    logger.info("Cookie validation requested", provider=provider)

    try:
        is_valid = await cookie_service.validate_cookie(provider)

        age_hours = cookie_service.get_cookie_age_hours(provider)
        warning = cookie_service.check_cookie_age(provider)

        return CookieValidationResponse(
            provider=provider,
            is_valid=is_valid,
            age_hours=age_hours,
            warning=warning,
        )

    except CookieError as e:
        logger.error("Cookie validation failed", provider=provider, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "COOKIE_VALIDATION_FAILED",
                "message": str(e),
                "provider": provider,
            },
        )
    except Exception as e:
        logger.error(
            "Unexpected error during cookie validation",
            provider=provider,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred during cookie validation",
            },
        )


@router.post("/reload-cookie", response_model=CookieReloadResponse)
async def reload_cookie(
    provider: str,
    cookie_service: CookieService = Depends(get_cookie_service),  # noqa: B008
) -> Any:
    """
    Reload cookie file for a provider.

    This endpoint reloads the cookie file from disk, validates it,
    and rolls back if validation fails.

    Args:
        provider: Provider name (e.g., "youtube")
        cookie_service: Cookie service instance

    Returns:
        Reload result with success status

    Raises:
        HTTPException: If reload fails
    """
    logger.info("Cookie reload requested", provider=provider)

    try:
        result = await cookie_service.reload_cookie(provider)

        return CookieReloadResponse(**result)

    except CookieError as e:
        logger.error("Cookie reload failed", provider=provider, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "COOKIE_RELOAD_FAILED",
                "message": str(e),
                "provider": provider,
            },
        )
    except Exception as e:
        logger.error(
            "Unexpected error during cookie reload",
            provider=provider,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred during cookie reload",
            },
        )
