"""
Prompt injection prevention for LLM inputs.

Sanitizes code snippets before they are embedded in LLM prompts to prevent
malicious content from hijacking the model's behavior.
"""

import re


def sanitize_code_for_llm(code: str, max_length: int = 50000) -> str:
    """
    Sanitize a code snippet before sending it to an LLM.

    Removes prompt injection patterns, control characters, and enforces a
    length limit so that untrusted source files cannot hijack the model.

    Args:
        code: Raw code snippet to sanitize
        max_length: Maximum allowed character count (default: 50000)

    Returns:
        Sanitized code snippet safe for embedding in LLM prompts
    """
    if not code:
        return ""

    dangerous_patterns = [
        r"\\b(?:ignore|reset|reset\\s+chat)\\b",
        r"\\b(?:system|assistant|user)\\s*:\\s*",
        r"<<\\|.*?>>",        # Heredoc patterns
        r"`[^`]*`[^`]*`",    # Triple backticks with injection
        r"\\$\\{[^}]*\\}",   # Shell variables
        r"\\$\\([^)]*\\)",   # Command substitution
    ]

    sanitized = code
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

    # Remove control characters except newlines and tabs
    sanitized = "".join(c for c in sanitized if c.isprintable() or c in "\n\t")

    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "\n... [truncated due to length]"

    # Strip excessive whitespace per line
    sanitized = "\n".join(line.strip() for line in sanitized.split("\n"))

    return sanitized
