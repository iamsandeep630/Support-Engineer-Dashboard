"""
Code Repository Port (Outbound Driven Port)
Defines abstract interface for Git repository providers (e.g., GitHub, GitLab, local git clone).
"""
from typing import Protocol, runtime_checkable, Optional, Dict, Any, List


@runtime_checkable
class ICodeRepositoryPort(Protocol):
    """Outbound port for code inspection and Git commits."""

    def get_file_contents(self, path: str) -> Optional[str]:
        """Fetches the raw text content of a file in the repository."""
        ...

    def search_code(self, query: str) -> Dict[str, Any]:
        """Searches symbols and text across the repository codebase."""
        ...

    def list_commits(self, path: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Lists recent commits in the target repository branch."""
        ...

    def commit_file_change(self, path: str, content: str, commit_message: str) -> Dict[str, Any]:
        """Applies a code change and commits it to the repository."""
        ...
