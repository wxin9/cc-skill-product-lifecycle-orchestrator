"""
Condition Evaluator for Product-Lifecycle Orchestrator.

Safely evaluates condition expressions for conditional branching.
"""
from __future__ import annotations
import re
from typing import Any, Dict, Optional


class ConditionEvaluator:
    """
    Safely evaluates condition expressions for phase branching.

    Supported operators:
      - Comparison: ==, !=, <, >, <=, >=
      - Logical: and, or, not
      - Membership: in, not in
      - Boolean literals: True, False
      - String literals: "value", 'value'
      - Number literals: 123, 45.6

    Context variables:
      - project_type: str (web, cli, mobile, data-pipeline, microservices)
      - has_prd: bool
      - has_architecture: bool
      - iteration_count: int
      - Any checkpoint metadata field
    """

    # Allowed operators and functions
    SAFE_OPERATORS = {
        '==', '!=', '<', '>', '<=', '>=',
        'and', 'or', 'not',
        'in', 'not in',
        'True', 'False', 'None'
    }

    def __init__(self, context: Dict[str, Any] = None):
        """
        Initialize ConditionEvaluator with context variables.

        Args:
            context: Dictionary of context variables for evaluation
        """
        self.context = context or {}

    def evaluate(self, expression: str, additional_context: Dict[str, Any] = None) -> bool:
        """
        Safely evaluate a condition expression.

        Args:
            expression: Condition expression to evaluate
            additional_context: Additional context variables

        Returns:
            Boolean result of evaluation

        Raises:
            ValueError: If expression is invalid or unsafe
        """
        if not expression or not expression.strip():
            return True  # Empty expression always evaluates to True

        # Merge contexts
        context = {**self.context, **(additional_context or {})}

        # Validate expression
        self._validate_expression(expression)

        # Safely evaluate
        try:
            # Create restricted namespace
            safe_namespace = {
                '__builtins__': {},  # Disable builtins
                **context
            }

            # Evaluate expression
            result = eval(expression, safe_namespace, {})

            # Ensure result is boolean
            return bool(result)

        except Exception as e:
            raise ValueError(f"Failed to evaluate expression '{expression}': {e}")

    def _validate_expression(self, expression: str):
        """
        Validate that expression only contains safe operators.

        Raises:
            ValueError: If expression contains unsafe constructs
        """
        # Check for forbidden patterns
        forbidden_patterns = [
            r'__\w+__',  # Dunder methods
            r'import\s',  # Import statements
            r'exec\s*\(',  # exec function
            r'eval\s*\(',  # eval function
            r'open\s*\(',  # open function
            r'file\s*\(',  # file function
            r'compile\s*\(',  # compile function
            r'getattr\s*\(',  # getattr function
            r'setattr\s*\(',  # setattr function
            r'delattr\s*\(',  # delattr function
            r'globals\s*\(',  # globals function
            r'locals\s*\(',  # locals function
            r'vars\s*\(',  # vars function
            r'dir\s*\(',  # dir function
        ]

        for pattern in forbidden_patterns:
            if re.search(pattern, expression):
                raise ValueError(f"Expression contains forbidden pattern: {pattern}")

        # Extract tokens
        tokens = self._tokenize(expression)

        # Check each token
        for token in tokens:
            # Skip string literals
            if (token.startswith('"') and token.endswith('"')) or \
               (token.startswith("'") and token.endswith("'")):
                continue

            # Skip numbers
            if re.match(r'^\d+\.?\d*$', token):
                continue

            # Skip context variables (alphanumeric + underscore)
            if re.match(r'^[a-zA-Z_]\w*$', token):
                continue

            # Check if it's a safe operator
            if token not in self.SAFE_OPERATORS:
                # Could be a context variable, allow it
                pass

    def _tokenize(self, expression: str) -> list:
        """
        Tokenize expression into operators and operands.

        Returns:
            List of tokens
        """
        # Simple tokenization: split by operators and whitespace
        tokens = re.split(r'(\s+|==|!=|<=|>=|<|>|and|or|not|in)', expression)

        # Filter out empty strings and whitespace
        tokens = [t.strip() for t in tokens if t.strip()]

        return tokens

    def update_context(self, context: Dict[str, Any]):
        """Update context variables."""
        self.context.update(context)

    def get_context(self) -> Dict[str, Any]:
        """Get current context."""
        return self.context.copy()


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

def evaluate_condition(
    expression: str,
    checkpoint: dict,
    additional_context: Dict[str, Any] = None
) -> bool:
    """
    Evaluate condition expression with checkpoint context.

    Args:
        expression: Condition expression
        checkpoint: Checkpoint dictionary
        additional_context: Additional context variables

    Returns:
        Boolean result
    """
    # Build context from checkpoint
    context = {
        'project_type': checkpoint.get('metadata', {}).get('project_type', 'unknown'),
        'has_prd': checkpoint.get('metadata', {}).get('has_prd', False),
        'has_architecture': checkpoint.get('metadata', {}).get('has_architecture', False),
        'iteration_count': checkpoint.get('metadata', {}).get('current_iteration', 0),
        'status': checkpoint.get('status', 'unknown'),
        'intent': checkpoint.get('intent', 'unknown'),
    }

    # Add all metadata fields
    context.update(checkpoint.get('metadata', {}))

    # Create evaluator
    evaluator = ConditionEvaluator(context)

    # Evaluate
    return evaluator.evaluate(expression, additional_context)
