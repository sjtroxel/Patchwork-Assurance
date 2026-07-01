"""The permitted/prohibited-language guard (.claude/rules/legal-content.md), in core/ so both the
Phase 11 render test and the Phase 12 reviewer agent enforce the SAME list. Words that assert
authoritative legal judgment or a guarantee must never appear in generated copy — the not-legal-advice
boundary made mechanical.
"""

# Kept byte-for-byte in sync with the render test's historical list (mirrors core.prompts' prohibited
# framing). Matched case-insensitively as substrings.
PROHIBITED = ("guarantee", "you are compliant", "you must comply", "we certify")


def has_prohibited_language(text: str) -> bool:
    """True if `text` contains any prohibited, over-claiming phrase (case-insensitive)."""
    lower = (text or "").lower()
    return any(bad in lower for bad in PROHIBITED)
