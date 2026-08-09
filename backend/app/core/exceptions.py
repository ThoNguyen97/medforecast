"""Custom exceptions for the application."""
from fastapi import HTTPException, status


class MedForecastException(Exception):
    """Base exception for MedForecast application."""
    pass


class AuthenticationError(MedForecastException):
    """Authentication related errors."""
    pass


class AuthorizationError(MedForecastException):
    """Authorization related errors."""
    pass


class ValidationError(MedForecastException):
    """Data validation errors."""
    pass


class NotFoundError(MedForecastException):
    """Resource not found errors."""
    pass


# HTTP Exception helpers
def http_401_unauthorized(detail: str = "Could not validate credentials"):
    """Return 401 Unauthorized HTTP exception."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def http_403_forbidden(detail: str = "Not enough permissions"):
    """Return 403 Forbidden HTTP exception."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def http_404_not_found(detail: str = "Resource not found"):
    """Return 404 Not Found HTTP exception."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


def http_422_validation_error(detail: str = "Validation error"):
    """Return 422 Validation Error HTTP exception."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=detail,
    )