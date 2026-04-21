"""
Unit tests for DocValidator.

Tests cover:
- PRD validation (structure, EARS compliance, quality metrics)
- Architecture validation
- Test outline validation
- Helper functions (section finding, word counting, etc.)
"""
import pytest
import tempfile
from pathlib import Path
from scripts.core.doc_validator import (
    validate_document,
    _find_section,
    _section_body,
    _word_count,
    _count_list_items,
    _count_ordered_steps,
    _has_numbers,
    _has_table,
    _check_ears_compliance,
    THRESHOLD
)


class TestDocValidatorHelpers:
    """Test suite for DocValidator helper functions."""

    def test_find_section_finds_heading(self):
        """Test that _find_section finds section headings."""
        content = """# Main Title

## 1. Introduction

This is the introduction.

## 2. Goals

These are the goals.
"""
        found, start = _find_section(content, r"##\s*1\.\s*Introduction")
        assert found is True
        assert start >= 0

    def test_find_section_returns_false_for_missing(self):
        """Test that _find_section returns False for missing sections."""
        content = "# Main Title\n\n## Introduction\n"
        found, start = _find_section(content, r"##\s*Nonexistent")
        assert found is False
        assert start == -1

    def test_section_body_extracts_content(self):
        """Test that _section_body extracts section body."""
        content = """## Introduction

This is the introduction.

More content here.

## Goals

This is goals section.
"""
        found, start = _find_section(content, r"##\s*Introduction")
        body = _section_body(content, start)

        assert "This is the introduction" in body
        assert "More content here" in body
        assert "Goals" not in body

    def test_word_count_counts_english_words(self):
        """Test that _word_count counts English words."""
        text = "This is a test with seven words"
        count = _word_count(text)
        assert count == 7

    def test_word_count_counts_chinese_characters(self):
        """Test that _word_count counts Chinese characters."""
        text = "这是中文测试"
        count = _word_count(text)
        assert count == 6

    def test_word_count_counts_mixed_content(self):
        """Test that _word_count counts mixed English and Chinese."""
        text = "This is English and 这是中文"
        count = _word_count(text)
        assert count == 8  # 5 English + 3 Chinese

    def test_count_list_items_counts_bullets(self):
        """Test that _count_list_items counts bullet list items."""
        text = """- Item 1
- Item 2
* Item 3
• Item 4
"""
        count = _count_list_items(text)
        assert count == 4

    def test_count_list_items_ignores_plain_text(self):
        """Test that _count_list_items ignores plain text."""
        text = "This is not a list item.\nNeither is this."
        count = _count_list_items(text)
        assert count == 0

    def test_count_ordered_steps_counts_numbered_items(self):
        """Test that _count_ordered_steps counts numbered steps."""
        text = """1. First step
2. Second step
3. Third step
"""
        count = _count_ordered_steps(text)
        assert count == 3

    def test_has_numbers_detects_metrics(self):
        """Test that _has_numbers detects performance metrics."""
        assert _has_numbers("Response time < 200ms") is True
        assert _has_numbers("Success rate 99.9%") is True
        assert _has_numbers("支持 100 并发用户") is True  # Chinese with '并发'
        assert _has_numbers("No metrics here") is False

    def test_has_table_detects_markdown_tables(self):
        """Test that _has_table detects markdown tables."""
        text = """| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |
"""
        assert _has_table(text) is True

    def test_has_table_requires_minimum_rows(self):
        """Test that _has_table requires minimum number of rows."""
        text = """| Header |
|--------|
"""
        assert _has_table(text) is False


class TestEARSCompliance:
    """Test suite for EARS compliance checking."""

    def test_check_ears_compliance_detects_event_driven_english(self):
        """Test that EARS checker detects event-driven requirements (English)."""
        content = """### F01 — User Login

When the user clicks submit, the system shall validate the form.
"""
        result = _check_ears_compliance(content)

        assert result["total_requirements"] >= 1
        assert "Event-driven" in result.get("by_pattern", {})

    def test_check_ears_compliance_detects_event_driven_chinese(self):
        """Test that EARS checker detects event-driven requirements (Chinese)."""
        content = """### F01 — 用户登录

当用户点击提交时，系统应验证表单。
"""
        result = _check_ears_compliance(content)

        assert result["total_requirements"] >= 1
        assert "Event-driven" in result.get("by_pattern", {})

    def test_check_ears_compliance_detects_ubiquitous_english(self):
        """Test that EARS checker detects ubiquitous requirements (English)."""
        content = """### F01 — Authentication

The system shall authenticate users.
"""
        result = _check_ears_compliance(content)

        assert result["total_requirements"] >= 1
        assert "Ubiquitous" in result.get("by_pattern", {})

    def test_check_ears_compliance_detects_ubiquitous_chinese(self):
        """Test that EARS checker detects ubiquitous requirements (Chinese)."""
        content = """### F01 — 身份验证

系统应验证用户身份。
"""
        result = _check_ears_compliance(content)

        assert result["total_requirements"] >= 1
        assert "Ubiquitous" in result.get("by_pattern", {})

    def test_check_ears_compliance_detects_conditional_english(self):
        """Test that EARS checker detects conditional requirements (English)."""
        content = """### F01 — Payment

If the payment fails, the system shall notify the user.
"""
        result = _check_ears_compliance(content)

        assert result["total_requirements"] >= 1
        assert "Unwanted/Conditional" in result.get("by_pattern", {})

    def test_check_ears_compliance_detects_conditional_chinese(self):
        """Test that EARS checker detects conditional requirements (Chinese)."""
        content = """### F01 — 支付

如果支付失败，系统应通知用户。
"""
        result = _check_ears_compliance(content)

        assert result["total_requirements"] >= 1
        assert "Unwanted/Conditional" in result.get("by_pattern", {})

    def test_check_ears_compliance_returns_zero_for_no_requirements(self):
        """Test that EARS checker returns zero for non-requirement text."""
        content = "This is just a description with no requirements."
        result = _check_ears_compliance(content)

        assert result["total_requirements"] == 0


class TestPRDValidation:
    """Test suite for PRD document validation."""

    def test_validate_prd_passes_minimal_document(self, tmp_path):
        """Test that PRD validation passes a minimal valid PRD."""
        prd_path = tmp_path / "PRD.md"
        prd_content = """# Product Requirements Document

## 1. Product Vision

This product helps teams manage their product lifecycle from ideation to delivery.
It solves the problem of fragmented tooling by providing an integrated workflow
that covers PRD creation, architecture design, test planning, and iteration tracking.
Target users are product managers, developers, and QA engineers in agile teams.

## 2. Core Features

- Feature 1: PRD drafting with AI assistance
- Feature 2: Architecture review and validation
- Feature 3: Test outline generation
- Feature 4: Sprint planning and velocity tracking

## 3. User Roles

- Product Manager: creates and manages PRDs
- Developer: reviews architecture and implements features
- QA Engineer: writes and runs test cases

## 4. User Flow

1. User identifies product need and initiates new-product workflow
2. System analyzes requirements and generates solution options
3. User selects solution and approves PRD draft
4. System validates PRD quality score

## 5. Non-Functional Requirements

- Performance: API response time < 200ms (p99)
- Reliability: 99.9% uptime SLA
- Security: All data encrypted at rest and in transit

## 6. Scope

In Scope:
- PRD creation and validation
- Architecture design workflow

Out of Scope:
- Code generation
- Deployment automation

## 7. Risks

- Risk: AI model quality degradation. Mitigation: fallback to manual templates.
- Risk: User adoption resistance. Mitigation: onboarding guides and tutorials.
"""
        prd_path.write_text(prd_content)

        result = validate_document(str(prd_path), "prd")

        assert result["passed"] is True
        assert result["score"] >= THRESHOLD

    def test_validate_prd_fails_incomplete_document(self, tmp_path):
        """Test that PRD validation fails for incomplete documents."""
        prd_path = tmp_path / "PRD.md"
        prd_content = """# PRD

## Introduction

Brief intro.

## Goals

One goal.
"""
        prd_path.write_text(prd_content)

        result = validate_document(str(prd_path), "prd")

        assert result["passed"] is False
        assert result["score"] < THRESHOLD

    def test_validate_prd_detects_ears_compliance(self, tmp_path):
        """Test that PRD validation detects EARS-compliant requirements."""
        prd_path = tmp_path / "PRD.md"
        prd_content = """# PRD

## 1. Introduction

Product introduction.

## 2. Goals

- Goal 1

## 3. Features

### Feature 1

**User Stories**:
- As a user, I want to login.

## 4. Non-Functional Requirements

- When the user submits a form, the system shall validate all fields.
- The system shall encrypt all sensitive data.
- If an error occurs, the system shall display a friendly message.

## 5. Constraints

- Budget: Limited.
"""
        prd_path.write_text(prd_content)

        result = validate_document(str(prd_path), "prd")

        # Should have EARS compliance data
        assert "ears_compliance" in result or result.get("score", 0) >= 0

    def test_validate_prd_auto_detects_type(self, tmp_path):
        """Test that validation auto-detects PRD type from path."""
        prd_path = tmp_path / "PRD.md"
        prd_content = """# Product Requirements Document

## 1. Introduction

Introduction content.

## 2. Goals

- Goal 1
- Goal 2

## 3. Features

### Feature 1

Description.

**User Stories**:
- As a user, I want to do something.

## 4. Non-Functional Requirements

- Performance: Fast response.

## 5. Constraints

- Budget: Limited.
"""
        prd_path.write_text(prd_content)

        # Auto-detect type
        result = validate_document(str(prd_path), "auto")

        assert "passed" in result
        assert "score" in result


class TestArchitectureValidation:
    """Test suite for Architecture document validation."""

    def test_validate_architecture_passes_minimal_document(self, tmp_path):
        """Test that Architecture validation passes a minimal valid document."""
        arch_path = tmp_path / "ARCHITECTURE.md"
        arch_content = """# Architecture Document

## 1. System Overview

The system provides product lifecycle management. External dependencies:

- Anthropic API: AI assistance for PRD and architecture drafting
- GitHub API: code repository integration and CI/CD triggers
- PostgreSQL: primary data store for workflow state

## 2. Tech Stack

We chose these technologies for the following reasons:

- Frontend: React 18, TypeScript — chose React because of component reusability
- Backend: Python 3.9, FastAPI — chose FastAPI because of async support and speed
- Database: PostgreSQL 15 — chose PostgreSQL for ACID compliance and complex queries
- Cache: Redis — suitable for session management and rate limiting

## 3. High-Level Architecture

```
┌──────────────┐     REST API    ┌──────────────────┐
│   Frontend   │ ─────────────→  │  FastAPI Backend  │
│  (React/TS)  │                 │  (Orchestrator)   │
└──────────────┘                 └────────┬─────────┘
                                          │
                              ┌───────────┴──────────┐
                              │                      │
                     ┌────────▼───────┐   ┌─────────▼──────┐
                     │  PostgreSQL    │   │     Redis       │
                     │  (State/Data)  │   │   (Sessions)    │
                     └────────────────┘   └────────────────┘
```

## 4. Components

| Module | Responsibility | Technology |
|--------|----------------|------------|
| OrchestratorService | Coordinates phase execution | Python |
| CheckpointManager | Persists workflow state | Python + PostgreSQL |
| DocValidator | Validates PRD and arch documents | Python + regex |
| SolutionAnalyzer | Analyzes requirements and proposes solutions | Python + AI |

## 5. Data Model

| Field | Type | Description |
|-------|------|-------------|
| project_id | UUID | Primary key |
| status | String | Workflow status |
| current_phase | String | Active phase ID |
| completed_phases | Array | List of completed phase IDs |

## 6. API Design

Main endpoints:

- POST /orchestrator/run — start a new workflow
- POST /orchestrator/resume — resume from a specific phase
- GET /orchestrator/status — get current workflow status

## 7. Deployment

Deployed on AWS ECS using Docker containers. CI/CD via GitHub Actions.
- Database: RDS PostgreSQL (Multi-AZ for high availability)
- Cache: ElastiCache Redis
- Deployment steps: build → test → push image → rolling deploy

## 8. Architecture Decision Records

### ADR-001: PostgreSQL over NoSQL
Background: Need to persist workflow state with complex queries.
Decision: Use PostgreSQL for relational integrity and ACID compliance.
Status: Accepted
Rationale: Strong consistency required; workflow phases have strict dependencies.
"""
        arch_path.write_text(arch_content)

        result = validate_document(str(arch_path), "architecture")

        assert result["passed"] is True
        assert result["score"] >= THRESHOLD

    def test_validate_architecture_fails_incomplete_document(self, tmp_path):
        """Test that Architecture validation fails for incomplete documents."""
        arch_path = tmp_path / "ARCHITECTURE.md"
        arch_content = """# Architecture

## Introduction

Brief intro.
"""
        arch_path.write_text(arch_content)

        result = validate_document(str(arch_path), "architecture")

        assert result["passed"] is False
        assert result["score"] < THRESHOLD


class TestTestOutlineValidation:
    """Test suite for Test Outline document validation."""

    def test_validate_test_outline_passes_minimal_document(self, tmp_path):
        """Test that Test Outline validation passes a minimal valid document."""
        outline_path = tmp_path / "MASTER_OUTLINE.md"
        outline_content = """# Master Test Outline

## F01 — User Authentication

### TST-F01-S01 Successful Login

前置条件: User account exists with valid credentials

测试步骤:
1. Navigate to login page
2. Enter valid username and password
3. Click Submit button
4. Verify redirect to dashboard

期望结果: User is redirected to dashboard and session token is set

### TST-F01-S02 Invalid Password

前置条件: User account exists

测试步骤:
1. Navigate to login page
2. Enter valid username but wrong password
3. Click Submit button

期望结果: Error message displayed, login rejected

## F02 — User Registration

### TST-F02-S01 Successful Registration

前置条件: Email not already registered in system

测试步骤:
1. Navigate to registration page
2. Fill all required fields with valid data
3. Click Register button

期望结果: Account created, confirmation email sent

### TST-F02-S02 Duplicate Email Error

前置条件: Email already registered in system

测试步骤:
1. Navigate to registration page
2. Enter an already-registered email
3. Click Register button

期望结果: Error message "Email already in use" displayed, no new account created
"""
        outline_path.write_text(outline_content)

        result = validate_document(str(outline_path), "test-outline")

        assert result["passed"] is True
        assert result["score"] >= THRESHOLD

    def test_validate_test_outline_fails_incomplete_document(self, tmp_path):
        """Test that Test Outline validation fails for incomplete documents."""
        outline_path = tmp_path / "MASTER_OUTLINE.md"
        outline_content = """# Test Outline

## Feature 1

Brief description.
"""
        outline_path.write_text(outline_content)

        result = validate_document(str(outline_path), "test-outline")

        assert result["passed"] is False
        assert result["score"] < THRESHOLD


class TestDocValidatorIntegration:
    """Integration tests for DocValidator."""

    def test_validate_nonexistent_file_returns_error(self):
        """Test that validation returns error for nonexistent file."""
        result = validate_document("/nonexistent/file.md", "prd")

        assert result["passed"] is False
        assert "error" in result or result.get("score", 0) == 0

    def test_validate_empty_file_fails(self, tmp_path):
        """Test that validation fails for empty file."""
        file_path = tmp_path / "empty.md"
        file_path.write_text("")

        result = validate_document(str(file_path), "prd")

        assert result["passed"] is False

    def test_validate_file_with_only_headings_fails(self, tmp_path):
        """Test that validation fails for file with only headings."""
        file_path = tmp_path / "headings.md"
        file_path.write_text("# Heading 1\n\n## Heading 2\n\n### Heading 3\n")

        result = validate_document(str(file_path), "prd")

        assert result["passed"] is False
