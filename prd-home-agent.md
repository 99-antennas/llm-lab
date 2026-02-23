# PRD: Home AI Agent Server

File: prd-home-agent.md\
Version: v6\
Status: Active\
Target Builder: Autonomous Coding Agent\
Initial Deployment: macOS (M1 laptop)\
Future Deployment: Linux mini PC
Serve as an accessible UI to run local models to perform basic tasks as needed without sending PII to the cloud.
Supported features/mini-apps:
    - reminding me to study for Math GRE's and providing a question each day
    - archiving files to Google Cloud Storage intelligently (/Users/kas/dev/archiver/archiver) 
    - reading and prioritizing email 
    - checking slack hourly 
    - deleting duplicate or non-important photos 
    - other personal tasks as needed (i.e. checking flight costs, etc.)

------------------------------------------------------------------------

# 1. Product Vision

Build a self-hosted hybrid AI agent platform that:

-   Runs on macOS initially
-   Migrates cleanly to Linux
-   Uses Google Secret Manager as secret vault
-   Supports:
    -   Voice push-to-talk from phone + laptop
    -   Hybrid LLM routing (Ollama + external API)
    -   Modular MCP tool servers
    -   Approval-based execution of destructive actions
    -   Multi-user-ready authentication (single-user enabled in v1)
    -   GitHub polling-based deployment
-   Is secure, restart-safe, migration-ready, observable, and extensible

This is a home server project.\
Prioritize simplicity, maintainability, low cost, and operational
clarity.

------------------------------------------------------------------------

# 2. Core Engineering Philosophy

1.  Everything runs in Docker.
2.  Keep infrastructure simple.
3.  Avoid unnecessary abstraction layers.
4.  Prefer clarity over cleverness.
5.  Favor low-cost and low-maintenance solutions.
6.  Design for multi-user, but implement single-user.
7.  Build for long-term maintainability.
8.  Prefer local models for features that access personal data to protect privacy. 

------------------------------------------------------------------------

# 3. Code Requirements

## 3.1 Use of Data Models

### Pydantic Usage

-   All API request and response schemas must use Pydantic models.
-   Any method with more than two arguments must:
    -   Accept a Pydantic request model.
    -   Return a Pydantic response model.

### Model Organization

All models must be separated into:

apps/api/models/

Sub-structure:

models/ api/ domain/ db/

### Domain vs Database Models

Domain Models: - Represent business logic. - May include computed
fields. - Used in services and tool routing.

Database Models: - Represent actual DB tables. - Enforce schema
constraints. - No business logic.

Never mix business logic into DB models.

### Python Package Management

-   Use `uv` as the required Python package manager and task runner.
-   Store dependencies in `pyproject.toml` and lock with `uv.lock`.
-   Run tests and project commands through `uv run ...`.
-   Do not use ad-hoc global installs or unmanaged virtualenv flows.

## 3.2 Clients Directory and Secret Loading

-   Add a top-level `/clients` directory for third-party integrations (for
    example: Google Cloud, Gmail, Google Drive, Google Cloud Storage, Slack).
-   Use a master config file for project configuration (skills, apps, and
    integration settings).
-   Non-secret values may be stored as plain config values or environment
    values.
-   Secrets must be referenced as `gsm://...` and resolved through Google
    Secret Manager.
-   Bootstrap access uses service account credentials (`GOOGLE_CLOUD_PROJECT`,
    `GOOGLE_APPLICATION_CREDENTIALS`) with no human sign-in on server.
-   Required flow:
    `config -> secret manager -> client -> instantiated client`
-   Provide a shared Google client factory named `get_google_cloud`.
-   Reuse the shared Google client for Google services (Secret Manager, Gmail,
    Drive, Cloud Storage).
-   Client instantiation must fail fast if required secrets cannot be
    retrieved.

------------------------------------------------------------------------

# 4. Logging Requirements

-   Use structured JSON logging.
-   Include: timestamp, level, module, function, user_id, request_id.
-   Log when functions start and complete.
-   Log argument values in errors (excluding secrets).
-   Use logger.exception() for critical errors.
-   Raise explicit custom exceptions.
-   API must convert domain exceptions to proper HTTP status codes.

------------------------------------------------------------------------

# 5. Testing Requirements

## Database Testing

-   Use a real Postgres test database.
-   Do not mock internal DB calls.
-   Use transaction rollback or isolated schemas.

## Mocking Policy

-   Third-party network calls may be mocked.

-   At least one integration test must call the real external API.

-   Integration tests may be skipped in CI if credentials missing.

-   ≥ 80% coverage for core modules.

------------------------------------------------------------------------

# 6. Hybrid Model Routing

-   Support Ollama (local) and external API models.
-   Implement a redaction layer before external calls.
-   Do not send raw images externally by default.
-   Prefer local summarization before external calls.

------------------------------------------------------------------------

# 7. MCP Tool Architecture

-   Gateway implements MCP client.
-   HTTP transport for MCP servers.
-   tools.yaml registry.
-   Tool discovery at startup.
-   Centralized approval enforcement.

## Tool Versioning

Each tool must expose: - tool_name - tool_version - supported_actions

Log tool version in audit logs.

## Timeout Policy

-   Default timeout: 10 seconds.
-   Retries only for idempotent operations.

## Idempotency

-   Detect duplicate uploads and sends.
-   Avoid duplicate file operations.

------------------------------------------------------------------------

# 8. Polling-Based Deployment

-   Poll GitHub every 60 seconds (configurable).
-   Fast-forward only pull.
-   Lock to prevent concurrent deploy.
-   Backoff after 3 failures (pause 15 minutes).
-   Manual pause file: DEPLOY_PAUSED.

Deploy script must: - Build before restart. - Run migrations. - Run
health checks. - Log commit SHA.

------------------------------------------------------------------------

# 9. Secrets Management (Google Secret Manager)

-   Dedicated Google Cloud project for secrets.
-   Use Google Secret Manager API for secret retrieval.
-   Server secret references use `gsm://...`.
-   No secrets committed to repo.
-   No plaintext secret storage.
-   Rotating secrets requires no code change.

------------------------------------------------------------------------

# 10. Database & Backup

-   Nightly pg_dump.
-   Retain last 7 backups.
-   Restore procedure documented and tested.

------------------------------------------------------------------------

# 11. Observability

-   Structured logs.
-   Audit logs with tool version.
-   Task history.
-   Polling logs.
-   Health endpoints.
-   Support bundle script.

------------------------------------------------------------------------

# 12. Security

-   Tailscale-only access.
-   No public ports.
-   HTTP-only secure cookies.
-   Approval required for destructive actions.
-   All destructive actions logged.

------------------------------------------------------------------------

# 13. Migration Requirements

-   No OS-specific paths.
-   Ollama base URL configurable.
-   Same deploy scripts on Linux.
-   Replace launchd with systemd timer.
-   No code changes required.

Migration success: - Copy repo. - Configure GCP credentials. - docker
compose up -d. - System operational \< 30 minutes.

------------------------------------------------------------------------

# 14. Definition of Done

-   Auth required and user-scoped.
-   Voice works on phone + laptop.
-   Hybrid routing operational.
-   ≥ 3 MCP tools functional.
-   Approval workflow enforced.
-   Polling deploy operational.
-   Google Secret Manager integration operational.
-   Nightly DB backup working.
-   Test DB infra operational.
-   No cross-user data leakage.
-   All success metrics met.

------------------------------------------------------------------------

END OF PRD v6
