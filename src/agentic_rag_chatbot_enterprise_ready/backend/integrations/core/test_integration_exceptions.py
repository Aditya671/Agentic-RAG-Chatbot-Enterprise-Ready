"""Regression tests for the integration exception hierarchy."""

import pytest

from backend.integration.integration_exceptions import (
    IntegrationAuthenticationError,
    IntegrationAuthorizationError,
    IntegrationCapabilityError,
    IntegrationConfigurationError,
    IntegrationConnectionError,
    IntegrationConflictError,
    IntegrationError,
    IntegrationInternalError,
    IntegrationNotFoundError,
    IntegrationPolicyError,
    IntegrationProviderError,
    IntegrationRateLimitError,
    IntegrationStateError,
    IntegrationTimeoutError,
    IntegrationUnavailableError,
    IntegrationValidationError,
)


def test_base_error_is_runtime_error():
    error = IntegrationError("integration failed")

    assert isinstance(error, RuntimeError)
    assert str(error) == "integration failed"
    assert error.code == "integration_error"
    assert error.retryable is False
    assert error.user_safe is True


def test_context_is_preserved():
    error = IntegrationAuthenticationError(
        "Authentication failed.",
        provider="jira",
        connection_id="connection-123",
        operation="health_check",
        details={"status_code": 401},
    )

    assert error.provider == "jira"
    assert error.connection_id == "connection-123"
    assert error.operation == "health_check"
    assert error.details["status_code"] == 401


def test_to_dict_is_safe_and_structured():
    error = IntegrationAuthorizationError(
        "Operation is not permitted.",
        provider="sap",
        connection_id="sap-1",
        operation="query_entity_set",
        details={"status_code": 403},
    )

    payload = error.to_dict()

    assert payload == {
        "code": "integration_authorization_error",
        "message": "Operation is not permitted.",
        "provider": "sap",
        "connection_id": "sap-1",
        "operation": "query_entity_set",
        "retryable": False,
        "user_safe": True,
        "details": {"status_code": 403},
    }


def test_empty_message_is_rejected():
    with pytest.raises(ValueError):
        IntegrationError("")


def test_whitespace_message_is_rejected():
    with pytest.raises(ValueError):
        IntegrationError("   ")


@pytest.mark.parametrize(
    "credential_key",
    [
        "access_token",
        "refresh_token",
        "client_secret",
        "password",
        "api_key",
        "authorization",
    ],
)
def test_exception_details_reject_credentials(credential_key):
    with pytest.raises(ValueError):
        IntegrationError(
            "Unsafe exception details.",
            details={credential_key: "secret"},
        )


def test_rate_limit_is_retryable_and_preserves_retry_after():
    error = IntegrationRateLimitError(
        "Provider throttled the request.",
        provider="salesforce",
        retry_after=7.5,
    )

    assert error.retryable is True
    assert error.retry_after == 7.5
    assert error.to_dict()["retry_after"] == 7.5


def test_negative_retry_after_is_rejected():
    with pytest.raises(ValueError):
        IntegrationRateLimitError(
            "Invalid retry value.",
            retry_after=-1,
        )


@pytest.mark.parametrize(
    "error_type,expected_code,expected_retryable",
    [
        (IntegrationConfigurationError, "integration_configuration_error", False),
        (IntegrationNotFoundError, "integration_not_found", False),
        (IntegrationAuthenticationError, "integration_authentication_error", False),
        (IntegrationAuthorizationError, "integration_authorization_error", False),
        (IntegrationConnectionError, "integration_connection_error", True),
        (IntegrationTimeoutError, "integration_timeout", True),
        (IntegrationRateLimitError, "integration_rate_limit", True),
        (IntegrationValidationError, "integration_validation_error", False),
        (IntegrationCapabilityError, "integration_capability_error", False),
        (IntegrationPolicyError, "integration_policy_error", False),
        (IntegrationConflictError, "integration_conflict", False),
        (IntegrationStateError, "integration_state_error", False),
        (IntegrationProviderError, "integration_provider_error", False),
        (IntegrationUnavailableError, "integration_unavailable", True),
        (IntegrationInternalError, "integration_internal_error", False),
    ],
)
def test_exception_contracts(error_type, expected_code, expected_retryable):
    error = error_type("failure")

    assert error.code == expected_code
    assert error.retryable is expected_retryable
    assert isinstance(error, IntegrationError)


def test_internal_error_is_not_user_safe():
    error = IntegrationInternalError("Unexpected internal failure.")

    assert error.user_safe is False


def test_timeout_is_a_connection_error():
    error = IntegrationTimeoutError("Request timed out.")

    assert isinstance(error, IntegrationConnectionError)
    assert isinstance(error, IntegrationError)
    assert error.retryable is True


def test_unavailable_is_retryable():
    error = IntegrationUnavailableError("Service unavailable.")

    assert error.retryable is True


def test_details_are_copied():
    details = {"status_code": 500}
    error = IntegrationProviderError(
        "Provider failed.",
        details=details,
    )

    details["status_code"] = 999

    assert error.details["status_code"] == 500


def test_none_optional_context_is_allowed():
    error = IntegrationConfigurationError("Invalid configuration.")

    assert error.provider is None
    assert error.connection_id is None
    assert error.operation is None
    assert error.details == {}
