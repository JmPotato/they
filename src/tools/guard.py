"""File access guard — block sensitive file patterns."""

import fnmatch
from pathlib import Path

# Safe suffixes that look sensitive but aren't (templates, samples)
SAFE_SUFFIXES = (".example", ".sample", ".template")

# Patterns matched against the file name (not the full path)
SENSITIVE_NAMES = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.jks",
]

# Single-component directory names matched against path parts
SENSITIVE_DIRS = [
    ".ssh",
    ".gnupg",
    ".aws",
]

# Multi-component path fragments matched via substring of the resolved path
SENSITIVE_FRAGMENTS = [
    ".config/gcloud",
]


def check_path(file_path: str) -> str | None:
    """Return an error message if the path is sensitive, otherwise None."""
    p = Path(file_path)
    name = p.name

    # Allow templates like .env.example
    if name.endswith(SAFE_SUFFIXES):
        return None

    for pattern in SENSITIVE_NAMES:
        if fnmatch.fnmatch(name, pattern):
            return f"Skipped: {name} is a sensitive file and cannot be accessed."

    resolved = p.resolve()
    parts = resolved.parts
    for dirname in SENSITIVE_DIRS:
        if dirname in parts:
            return f"Skipped: path contains sensitive directory '{dirname}'."

    resolved_str = str(resolved)
    for fragment in SENSITIVE_FRAGMENTS:
        if f"/{fragment}/" in resolved_str or resolved_str.endswith(f"/{fragment}"):
            return f"Skipped: path contains sensitive directory '{fragment}'."

    return None
