# `aws_credential_manager.py` — Upgrade Report

## Scope

This pass covers only the uploaded `aws_credential_manager.py`.

The source implements an `AWSCredentialManager` that:

- creates a Boto3 session,
- creates a Secrets Manager client,
- checks environment variables first,
- falls back to AWS Secrets Manager,
- supports `SecretString`,
- supports `SecretBinary`,
- and raises `ValueError` when a secret is unavailable. fileciteturn29file0

## Current dependency verification

Current PyPI information shows Boto3 **1.43.54** as the latest release I
verified, published July 22, 2026. Current Boto3 requires Python >=3.10. citeturn0search13turn0search5

The AWS Secrets Manager API still uses `GetSecretValue`, and AWS currently
recommends client-side caching for repeated secret retrieval because it reduces
latency and Secrets Manager API cost. citeturn0search1turn0search2

## Critical defect #1 — `Session()` does not prove credentials exist

The original code does:

```python
try:
    return boto3.session.Session()
except (NoCredentialsError, PartialCredentialsError):
    ...
```

The problem is that constructing a Boto3 `Session` does not necessarily perform
the complete credential-resolution operation.

The upgraded implementation calls:

```python
credentials = session.get_credentials()
```

and explicitly rejects:

```python
credentials is None
```

This makes the documented credential validation actually meaningful.

The manager still relies on Boto3's provider chain rather than constructing
static credentials.

## Critical defect #2 — credentials are never manually constructed

The upgraded code intentionally does not use:

```text
aws_access_key_id
aws_secret_access_key
aws_session_token
```

The application therefore remains compatible with:

- environment credentials,
- shared AWS profiles,
- AWS CLI configuration,
- EC2 instance roles,
- ECS task roles,
- Lambda execution roles,
- workload identity mechanisms supported by the SDK.

No long-lived credential is stored by this class.

## Critical defect #3 — overly narrow AWS error handling

Original code only catches:

```python
self.client.exceptions.ResourceNotFoundException
```

That misses important production failures such as:

- access denied,
- throttling,
- internal service failures,
- decryption failures,
- invalid requests.

The upgraded code catches `botocore.exceptions.ClientError`, identifies the
AWS error code, and converts it to an application-level `AWSSecretError`.

Importantly, it does not expose the raw AWS error message for access-denied
failures.

## Critical defect #4 — secret values must never appear in logs

The upgraded implementation contains no logging or printing of secret values.

AWS also warns that sensitive information should not be placed in request
parameters because Secrets Manager API calls are logged through CloudTrail.
citeturn0search6turn0search14

The class therefore deliberately avoids adding secret-value diagnostics.

## Critical defect #5 — environment lookup uses truthiness

Original:

```python
secret = os.environ.get(secret_name)
if secret:
    return secret
```

The upgraded implementation preserves the useful behavior of treating a
non-empty environment variable as a configured secret, while correctly handling
an AWS `SecretString` that happens to be an empty string.

The AWS response is checked by key presence rather than truthiness.

## Critical defect #6 — Secrets Manager client configuration

The upgraded client uses Botocore's `Config`:

```python
Config(
    retries={
        "mode": "standard",
        "max_attempts": ...,
    },
    connect_timeout=...,
    read_timeout=...,
)
```

This gives the application bounded retry and network-timeout behavior instead
of leaving the policy entirely implicit.

## Client-side caching

AWS currently recommends caching Secrets Manager values for repeated access.
citeturn0search0turn0search4

I added an **opt-in, per-manager TTL cache**:

```python
cache_ttl_seconds=0
```

The default is deliberately zero so the existing behavior remains:

```text
each AWS lookup → current Secrets Manager value
```

An application can opt into:

```python
cache_ttl_seconds=300
```

when the performance/cost benefit is more important than immediate retrieval
of rotated values.

The cache includes:

```python
clear_cache()
clear_cache(secret_name)
```

so an application can explicitly invalidate cached secrets.

This is intentionally not a dependency on a third-party caching package.

AWS's own Python caching component exists and AWS recommends client-side
caching, but AWS notes that its cache is not security hardened; if stronger
cache security is required, additional protection is necessary. citeturn0search0

For this application, keeping caching optional and local avoids silently
introducing another production dependency.

## SecretBinary handling

The upgraded implementation supports:

```text
SecretString
SecretBinary bytes
SecretBinary bytearray
SecretBinary string
```

and validates UTF-8 decoding for binary values.

Boto3's current `get_secret_value` API continues to return whichever of
`SecretString` or `SecretBinary` contains the secret. citeturn0search6

## Secret name handling

The upgraded implementation accepts both:

```text
environment-variable name
```

and:

```text
AWS Secrets Manager secret name / ARN
```

for the AWS lookup.

This is useful because AWS `SecretId` accepts the secret name or ARN.

## Backward compatibility

Preserved:

```python
AWSCredentialManager(
    secret_name=None,
    region_name="us-east-1",
)
```

and:

```python
manager.get_secret()
manager.get_secret("OTHER_SECRET")
manager.get_client()
manager.get_session()
```

The original environment-first lookup behavior remains.

## Regression suite

Added **50 regression tests** covering:

- default region
- custom region
- invalid names
- invalid regions
- environment precedence
- explicit secret-name override
- environment-only retrieval
- AWS SecretString
- empty SecretString
- SecretBinary
- invalid binary encoding
- malformed AWS responses
- ResourceNotFound
- AccessDenied
- throttling/other AWS errors
- original exception preservation
- missing credentials
- partial credentials
- Secrets Manager client construction
- standard retries
- network timeouts
- numeric configuration validation
- secret-safe implementation
- default cache behavior
- cache hits
- cache invalidation
- cache expiration
- environment/cache precedence
- instance isolation
- no static AWS keys
- no TLS disabling
- no wildcard secret enumeration
- current GetSecretValue API
- provider-chain usage

## Verification

Final regression suite:

```text
50 passed
```

**50/50 passed.**

The tests are dependency-isolated and do not call AWS.

## Production dependency recommendation

For the project dependency file, the current verified Boto3 release is:

```text
boto3==1.43.54
```

subject to the repository's global dependency compatibility/lock strategy.
Boto3 1.43.54 requires Python >=3.10. citeturn0search13

I did not blindly modify a project-wide requirements file because only this
single module was supplied in this turn.

## Important architectural observation

This class is named `AWSCredentialManager`, but its primary responsibility is
actually:

```text
AWS session/credential resolution
+
AWS Secrets Manager secret retrieval
```

It does **not** manage credentials in the sense of creating, rotating,
refreshing, or persisting AWS access credentials.

I did not rename the class because that would break the existing public API.

A future refactor could introduce:

```text
AWSSecretsManager
```

as the more precise abstraction while retaining:

```text
AWSCredentialManager
```

as a compatibility facade.

That is intentionally outside this file's safe upgrade scope.

## Security posture after upgrade

The intended flow is now:

```text
Application
    │
    ├── environment secret?
    │       └── return
    │
    └── AWS Secrets Manager
             │
             ├── Boto3 credential provider chain
             │
             ├── TLS
             │
             ├── bounded retries/timeouts
             │
             └── GetSecretValue
                      │
                      └── optional local TTL cache
```

No static AWS credentials are created or persisted by this component.

AWS's current Secrets Manager best-practice guidance also recommends storing
credentials/secrets in Secrets Manager, limiting access, rotating secrets, and
using caching appropriately. citeturn0search4

## Deliverables

- `aws_credential_manager_upgraded.py`
- `test_aws_credential_manager.py`
- `aws_credential_manager_upgrade_report.md`

## Integration verification still required

The unit/regression suite does not establish:

1. actual AWS IAM permissions,
2. actual Secrets Manager access,
3. KMS permissions for encrypted secrets,
4. ECS/EC2/Lambda workload identity,
5. AWS SSO/profile behavior,
6. secret rotation behavior,
7. production cache TTL policy.

Those require the application's real AWS environment and should be tested
separately.
