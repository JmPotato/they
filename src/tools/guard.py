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

# Patterns matched against any component of the path
SENSITIVE_PATHS = [
    ".ssh",
    ".gnupg",
    ".aws",
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

    parts = p.resolve().parts
    for pattern in SENSITIVE_PATHS:
        if pattern in parts:
            return f"Skipped: path contains sensitive directory '{pattern}'."

    return None
