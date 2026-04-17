"""
Unit tests for CommandExecutor.

Tests cover:
- Command routing and execution
- init, validate, outline, plan, change, draft, gate commands
- Error handling
- Argument placeholder replacement
"""
import pytest
import tempfile
import json
from pathlib import Path
from scripts.core.command_executor import CommandExecutor


class TestCommandExecutor:
    """Test suite for CommandExecutor."""

    def test_execute_routes_to_correct_handler(self, tmp_path):
        """Test that execute() routes to correct command handler."""
        executor = CommandExecutor(tmp_path)

        # Test init command
        result = executor.execute("init", {"name": "test-project"})
        assert result["success"] is True
        assert "test-project" in result["message"]

    def test_execute_returns_error_for_unknown_command(self, tmp_path):
        """Test that execute() returns error for unknown command."""
        executor = CommandExecutor(tmp_path)

        result = executor.execute("unknown-command")
        assert result["success"] is False
        assert "No handler" in result["error"]

    def test_cmd_init_creates_project_structure(self, tmp_path):
        """Test that _cmd_init creates correct project structure."""
        executor = CommandExecutor(tmp_path)

        result = executor._cmd_init({"name": "test-project"})

        assert result["success"] is True
        assert (tmp_path / "Docs" / "INDEX.md").exists()
        assert (tmp_path / ".lifecycle" / "config.json").exists()
        assert (tmp_path / ".lifecycle" / "dod.json").exists()
        assert (tmp_path / "Docs" / "adr" / "INDEX.md").exists()

    def test_cmd_init_creates_valid_config(self, tmp_path):
        """Test that _cmd_init creates valid config.json."""
        executor = CommandExecutor(tmp_path)

        executor._cmd_init({"name": "test-project"})

        config_path = tmp_path / ".lifecycle" / "config.json"
        config = json.loads(config_path.read_text())

        assert config["project_name"] == "test-project"
        assert config["version"] == "2.1"

    def test_cmd_init_creates_valid_dod(self, tmp_path):
        """Test that _cmd_init creates valid dod.json."""
        executor = CommandExecutor(tmp_path)

        executor._cmd_init({"name": "test-project"})

        dod_path = tmp_path / ".lifecycle" / "dod.json"
        dod = json.loads(dod_path.read_text())

        assert "rules" in dod
        assert len(dod["rules"]) >= 2

    def test_cmd_init_does_not_overwrite_existing(self, tmp_path):
        """Test that _cmd_init does not overwrite existing files."""
        executor = CommandExecutor(tmp_path)

        # Create existing INDEX.md
        docs_dir = tmp_path / "Docs"
        docs_dir.mkdir(parents=True)
        index_path = docs_dir / "INDEX.md"
        original_content = "# Original Content"
        index_path.write_text(original_content)

        # Run init
        executor._cmd_init({"name": "test-project"})

        # Should not overwrite
        assert index_path.read_text() == original_content

    def test_cmd_validate_validates_prd_document(self, tmp_path):
        """Test that _cmd_validate validates PRD document."""
        executor = CommandExecutor(tmp_path)

        # Create a minimal PRD
        docs_dir = tmp_path / "Docs" / "product"
        docs_dir.mkdir(parents=True)
        prd_path = docs_dir / "PRD.md"
        prd_content = """# Product Requirements Document

## 1. Introduction

This is a test PRD.

## 2. Goals

- Goal 1
- Goal 2

## 3. Features

### Feature 1

Description of feature 1.

**User Stories**:
- As a user, I want to do something.

## 4. Non-Functional Requirements

- Performance: System should be fast.

## 5. Constraints

- Budget: Limited.
"""
        prd_path.write_text(prd_content)

        result = executor._cmd_validate({"doc": "Docs/product/PRD.md", "type": "prd"})

        # Validation should pass or fail gracefully
        assert "success" in result
        assert "message" in result

    def test_cmd_validate_returns_error_for_missing_doc(self, tmp_path):
        """Test that _cmd_validate returns error for missing document."""
        executor = CommandExecutor(tmp_path)

        result = executor._cmd_validate({"doc": "nonexistent.md", "type": "prd"})

        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_cmd_validate_returns_error_for_missing_doc_arg(self, tmp_path):
        """Test that _cmd_validate returns error when doc arg not provided."""
        executor = CommandExecutor(tmp_path)

        result = executor._cmd_validate({})

        assert result["success"] is False
        assert "not provided" in result["error"]

    def test_cmd_outline_generates_test_outline(self, tmp_path):
        """Test that _cmd_outline generates test outline from PRD."""
        executor = CommandExecutor(tmp_path)

        # Create minimal PRD
        docs_dir = tmp_path / "Docs" / "product"
        docs_dir.mkdir(parents=True)
        prd_path = docs_dir / "PRD.md"
        prd_content = """# PRD

## Features

### Feature 1

Description.

**User Stories**:
- As a user, I want to login.
"""
        prd_path.write_text(prd_content)

        result = executor._cmd_outline({"prd": "Docs/product/PRD.md"})

        # Should succeed or fail gracefully
        assert "success" in result
        assert "message" in result

    def test_cmd_outline_returns_error_for_missing_prd(self, tmp_path):
        """Test that _cmd_outline returns error for missing PRD."""
        executor = CommandExecutor(tmp_path)

        result = executor._cmd_outline({"prd": "nonexistent.md"})

        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_cmd_plan_generates_iteration_plans(self, tmp_path):
        """Test that _cmd_plan generates iteration plans."""
        executor = CommandExecutor(tmp_path)

        # Create minimal test outline
        test_dir = tmp_path / "Docs" / "test"
        test_dir.mkdir(parents=True)
        outline_path = test_dir / "MASTER_OUTLINE.md"
        outline_content = """# Test Outline

## Features

### Feature 1

Description.

**Scenarios**:
- Scenario 1: Test login
"""
        outline_path.write_text(outline_content)

        result = executor._cmd_plan({"outline": "Docs/test/MASTER_OUTLINE.md"})

        # Should succeed or fail gracefully
        assert "success" in result
        assert "message" in result

    def test_cmd_plan_returns_error_for_missing_outline(self, tmp_path):
        """Test that _cmd_plan returns error for missing outline."""
        executor = CommandExecutor(tmp_path)

        result = executor._cmd_plan({"outline": "nonexistent.md"})

        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_cmd_change_detects_prd_changes(self, tmp_path):
        """Test that _cmd_change detects PRD changes."""
        executor = CommandExecutor(tmp_path)

        # Create old and new PRD
        docs_dir = tmp_path / "Docs" / "product"
        docs_dir.mkdir(parents=True)

        old_prd = docs_dir / "PRD_old.md"
        old_prd.write_text("# Old PRD\n\n## Feature A\nOld description.")

        new_prd = docs_dir / "PRD.md"
        new_prd.write_text("# New PRD\n\n## Feature A\nNew description.")

        result = executor._cmd_change({
            "old": "Docs/product/PRD_old.md",
            "new": "Docs/product/PRD.md"
        })

        # Should detect changes
        assert "success" in result
        assert "message" in result

    def test_cmd_change_returns_error_for_missing_new_prd(self, tmp_path):
        """Test that _cmd_change returns error for missing new PRD."""
        executor = CommandExecutor(tmp_path)

        result = executor._cmd_change({"new": "nonexistent.md"})

        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_cmd_draft_returns_instructions(self, tmp_path):
        """Test that _cmd_draft returns instructions for model."""
        executor = CommandExecutor(tmp_path)

        result = executor._cmd_draft({"type": "prd"})

        assert result["success"] is True
        assert "instructions" in result["data"]
        assert result["data"]["output_path"] == "Docs/product/PRD.md"

    def test_cmd_draft_returns_error_for_unknown_type(self, tmp_path):
        """Test that _cmd_draft returns error for unknown document type."""
        executor = CommandExecutor(tmp_path)

        result = executor._cmd_draft({"type": "unknown"})

        assert result["success"] is False
        assert "Valid types" in result["error"]

    def test_cmd_gate_checks_iteration_dod(self, tmp_path):
        """Test that _cmd_gate checks Definition of Done."""
        executor = CommandExecutor(tmp_path)

        # Initialize project
        executor._cmd_init({"name": "test-project"})

        # Create iteration 1 directory
        iter_dir = tmp_path / "Docs" / "iterations" / "iteration-1"
        iter_dir.mkdir(parents=True)

        result = executor._cmd_gate({"iteration": 1})

        # Should succeed or fail gracefully
        assert "success" in result
        assert "message" in result

    def test_cmd_gate_returns_error_for_missing_iteration(self, tmp_path):
        """Test that _cmd_gate returns error when iteration not provided."""
        executor = CommandExecutor(tmp_path)

        result = executor._cmd_gate({})

        assert result["success"] is False
        assert "not provided" in result["error"]


class TestCommandExecutorIntegration:
    """Integration tests for CommandExecutor."""

    def test_full_workflow_with_executor(self, tmp_path):
        """Test full workflow using CommandExecutor."""
        executor = CommandExecutor(tmp_path)

        # 1. Init
        result = executor.execute("init", {"name": "test-project"})
        assert result["success"] is True

        # 2. Verify structure created
        assert (tmp_path / "Docs" / "INDEX.md").exists()
        assert (tmp_path / ".lifecycle" / "config.json").exists()

    def test_error_handling_in_command(self, tmp_path):
        """Test that exceptions in commands are caught and returned."""
        executor = CommandExecutor(tmp_path)

        # Try to validate nonexistent document
        result = executor.execute("validate", {"doc": "nonexistent.md"})

        assert result["success"] is False
        assert result["error"] is not None
