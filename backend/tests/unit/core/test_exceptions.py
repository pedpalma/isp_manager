import pytest

from app.core.exceptions import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)


def test_app_exception_defaults():
    exc = AppException()
    assert exc.status_code == 500
    assert exc.error_code == "internal_error"
    assert exc.message == "AppException"
    assert exc.details is None


def test_custom_message_and_details():
    exc = NotFoundError("não achei", details={"id": "x"})
    assert exc.message == "não achei"
    assert exc.details == {"id": "x"}
    assert str(exc) == "não achei"


@pytest.mark.parametrize(
    ("cls", "status", "code"),
    [
        (NotFoundError, 404, "not_found"),
        (ValidationError, 422, "validation_error"),
        (ConflictError, 409, "conflict"),
        (AuthenticationError, 401, "authentication_error"),
        (AuthorizationError, 403, "authorization_error"),
        (ExternalServiceError, 502, "external_service_error"),
    ],
)
def test_subclass_mapping(cls, status, code):
    exc = cls()
    assert exc.status_code == status
    assert exc.error_code == code
    assert isinstance(exc, AppException)
