"""Environment variable loader utility."""

import os
from pathlib import Path


def load_env_file(env_path: Path | None = None) -> None:
    """
    Load environment variables from .env file.

    Args:
        env_path: Optional path to .env file. If None, looks for .env in project root.
    """
    if env_path is None:
        # Find project root by looking for pyproject.toml
        current_dir = Path(__file__).parent
        while current_dir != current_dir.parent:
            if (current_dir / "pyproject.toml").exists():
                env_path = current_dir / ".env"
                break
            current_dir = current_dir.parent

        if env_path is None:
            # Fallback to relative path
            env_path = Path(__file__).parent.parent.parent.parent / ".env"

    if not env_path.exists():
        return

    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=VALUE format
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]

                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value

    except Exception:  # nosec B110 - .env loading is intentionally optional
        # Silently ignore errors - .env is optional for development
        # Using pass here is intentional as missing .env files are expected
        pass


def get_project_root() -> Path:
    """
    Get the project root directory.

    Returns:
        Path to project root directory
    """
    current_dir = Path(__file__).parent
    while current_dir != current_dir.parent:
        if (current_dir / "pyproject.toml").exists():
            return current_dir
        current_dir = current_dir.parent

    # Fallback
    return Path(__file__).parent.parent.parent.parent
