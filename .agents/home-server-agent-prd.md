# PRD: Home Server Agent with Hermes and Mini-Apps

## Overview
Build a privacy-first home server on the always-on Mac laptop that serves as the primary agent layer for personal workflows. The server should be reachable from other Macs over SSH and from the phone through Slack, with SMS used for notifications and reminders. The system should stay simple, self-hosted, and easy to maintain.

## Problem Statement
The user wants a single home-server-based system that can:
- Accept tasks from the phone
- Manage files across the home network
- Automatically archive dropped files and make them searchable
- Support personal productivity workflows such as accounting, contact cleanup, email cleanup, and learning
- Avoid commercial services where possible because the information is sensitive
- Keep implementation effort low and avoid building unnecessary custom infrastructure

## Goals
- Provide a Slack-based interface for phone access
- Keep the Mac laptop as the always-on server
- Use Hermes as the orchestration and interaction layer
- Run small, focused mini-apps as separate Docker containers
- Automatically archive files from a watched folder into searchable storage
- Store file metadata in PostgreSQL for retrieval and search
- Send SMS notifications for cron jobs, reminders, and actionable tasks
- Keep the architecture simple, local-first, and maintainable

## Non-Goals
- Building a custom mobile app
- Migrating everything to a commercial SaaS platform
- Rewriting existing services that already work
- Designing a complex distributed system
- Adding unnecessary abstractions or microservices

## Proposed Solution
### System Layout
- The homeserver runs continuously on the Mac laptop.
- Hermes acts as the main agent layer for user interaction, scheduling, and task delegation.
- Mini-apps run as separate Dockerized services on the same machine.
- Slack is the primary user interface from the phone.
- SMS is used for notifications, cron reminders, and escalations.

### Mini-Apps
- Archiver: Watches a dedicated inbox folder, archives files automatically, stores metadata in PostgreSQL, and makes files retrievable.
- Contact Manager: Cleans, deduplicates, and exports contacts.
- Email Manager: Organizes inbox cleanup and archiving.
- Photo Manager: Handles photo organization and duplicate detection.

### Data Flow
1. A file is dropped into the watched folder.
2. The archiver detects the file, processes it, uploads it to object storage, and stores metadata in PostgreSQL.
3. The user asks Hermes in Slack to find the file.
4. Hermes queries the archiver metadata store.
5. The file is retrieved from storage and delivered to Slack, the homeserver, or Google Drive.

## User Stories
- As the user, I want to message the agent from Slack and get a task completed.
- As the user, I want dropped files to be archived automatically without manual intervention.
- As the user, I want to search for archived files by asking the LLM naturally.
- As the user, I want reminders and scheduled task notifications to come by SMS.
- As the user, I want to add new mini-apps without redesigning the core system.

## Functional Requirements
- The homeserver must run continuously.
- The system must expose a Slack-based interface.
- The system must support SMS notifications for scheduled jobs and actionable reminders.
- The archiver must watch a dedicated inbox folder for new files.
- The archiver must index file metadata in PostgreSQL.
- The system must support retrieval of archived files from storage.
- The architecture must allow additional mini-apps to be added as separate containers.
- The system should use SSH for access to other Macs on the home network.

## Constraints
- Sensitive information should not be sent to commercial services unless unavoidable.
- The user wants to build as little as possible.
- The implementation should remain simple and easy to maintain.
- The current environment already includes llm-lab and archiver FastAPI services.

## Recommended Architecture
- Hermes is the primary orchestration and interaction layer.
- llm-lab handles local-only processing that Hermes can call as a tool.
- Typical llm-lab responsibilities include file parsing, OCR, document transforms, and other host-local utilities.
- Archiver and future mini-apps remain separate services with narrow responsibilities.
- PostgreSQL is the shared metadata store.
- Docker Compose manages the services on the homeserver.
- Slack handles user interaction; SMS handles notifications.

## Open Questions
- Which Hermes deployment model is preferred for the homeserver?
- What exact accounting tasks are in scope?
- Should the learning app be a standalone mini-app or a Hermes skill?
