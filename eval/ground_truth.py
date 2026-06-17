"""
Structured ground truth for scoring the investigator, mirroring
taskhub-api's FAILURE_MATRIX.md.

Kept as a separate, hand-maintained structured file rather than
parsed from the markdown table at runtime -- the markdown is for
humans; this is for the eval harness. If FAILURE_MATRIX.md changes,
update this file to match.

category values must exactly match FailureCategory enum values in
app/models/state.py.
"""

GROUND_TRUTH = [
    {
        "branch": "break/dep-missing-jose",
        "category": "Dependency Failure",
        "broken_files": ["requirements.txt"],
    },
    {
        "branch": "break/dep-typo-package",
        "category": "Dependency Failure",
        "broken_files": ["requirements.txt"],
    },
    {
        "branch": "break/dep-version-conflict",
        "category": "Dependency Failure",
        "broken_files": ["requirements.txt"],
    },
    {
        "branch": "break/test-inverted-ownership",
        "category": "Test Failure",
        "broken_files": ["app/routers/tasks.py"],
    },
    {
        "branch": "break/test-plaintext-password",
        "category": "Test Failure",
        "broken_files": ["app/core/security.py"],
    },
    {
        "branch": "break/test-task-default-status",
        "category": "Test Failure",
        "broken_files": ["app/schemas/task.py"],
    },
    {
        "branch": "break/config-missing-secret-key",
        "category": "Configuration Failure",
        "broken_files": [".github/workflows/ci.yml"],
    },
    {
        "branch": "break/config-bad-algorithm",
        "category": "Configuration Failure",
        "broken_files": [".github/workflows/ci.yml"],
    },
    {
        "branch": "break/config-bad-expire-minutes",
        "category": "Configuration Failure",
        "broken_files": [".github/workflows/ci.yml"],
    },
    {
        "branch": "break/db-notnull-no-default",
        "category": "Database Failure",
        "broken_files": ["alembic/versions/a1b2c3d4e5f6_add_priority_column.py"],
    },
    {
        "branch": "break/db-wrong-fk-target",
        "category": "Database Failure",
        "broken_files": ["alembic/versions/b2c3d4e5f6a7_add_assigned_to_id.py"],
    },
    {
        "branch": "break/db-malformed-url",
        "category": "Database Failure",
        "broken_files": [".github/workflows/ci.yml"],
    },
    {
        "branch": "break/infra-bad-base-image",
        "category": "Infrastructure Failure",
        "broken_files": ["Dockerfile"],
    },
    {
        "branch": "break/infra-missing-healthcheck",
        "category": "Infrastructure Failure",
        "broken_files": ["docker-compose.yml"],
    },
    {
        "branch": "break/infra-dockerignore-excludes-app",
        "category": "Infrastructure Failure",
        "broken_files": [".dockerignore"],
    },
    {
        "branch": "break/build-bad-import",
        "category": "Build Failure",
        "broken_files": ["app/models/task.py"],
    },
    {
        "branch": "break/build-circular-import",
        "category": "Build Failure",
        "broken_files": ["app/models/task.py"],
    },
    {
        "branch": "break/build-bad-type-annotation",
        "category": "Build Failure",
        "broken_files": ["app/schemas/task.py"],
    },
]
