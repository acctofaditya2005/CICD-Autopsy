"""
Lightweight tech-stack detection.

Rather than a dedicated agent, this is a cheap, deterministic check
(no LLM call needed) that looks at root-level filenames to guess the
primary language/framework. The result is passed as context into
the classification and repo-investigation prompts so the LLM reasons
about the failure with the right assumptions (e.g. "this is a
Python/pytest project" vs "this is a Node/Jest project").

Intentionally simple: a few well-known marker files, checked in a
sensible priority order. Good enough to disambiguate the common
cases; not meant to handle complex polyglot monorepos.
"""

# Order matters: more specific/definitive markers first.
_MARKERS: list[tuple[str, str]] = [
    ("requirements.txt", "Python (pip)"),
    ("pyproject.toml", "Python (poetry/pyproject)"),
    ("Pipfile", "Python (pipenv)"),
    ("package.json", "Node.js / JavaScript / TypeScript"),
    ("go.mod", "Go"),
    ("Cargo.toml", "Rust"),
    ("pom.xml", "Java (Maven)"),
    ("build.gradle", "Java/Kotlin (Gradle)"),
    ("Gemfile", "Ruby"),
    ("composer.json", "PHP"),
    ("*.csproj", "C# / .NET"),
]


def detect_tech_stack(root_files: list[str]) -> str:
    """
    Given a list of filenames at the repo root, returns a short
    human-readable description of the likely primary tech stack.
    Falls back to "Unknown" if nothing recognizable is found.
    """
    lower_files = {f.lower() for f in root_files}

    for marker, label in _MARKERS:
        if marker.startswith("*."):
            ext = marker[1:]
            if any(f.endswith(ext) for f in lower_files):
                return label
        elif marker.lower() in lower_files:
            return label

    return "Unknown"
