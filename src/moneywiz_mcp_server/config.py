"""Configuration management for MoneyWiz MCP Server."""

from dataclasses import dataclass
import logging
import os
from pathlib import Path

from .utils.env_loader import load_env_file

logger = logging.getLogger(__name__)

# Container IDs for MoneyWiz 3: direct download, App Store, and Setapp builds.
_MONEYWIZ_CONTAINERS = (
    "com.moneywiz.mac",
    "com.moneywiz.personalfinance",
    "com.moneywiz.personalfinance-setapp",
)

_DB_SUFFIXES = frozenset({".sqlite", ".sqlite3", ".db"})


def moneywiz_search_dirs(home: Path | None = None) -> list[Path]:
    """Return directories that may hold the MoneyWiz database, most preferred first.

    Enabling iCloud sync moves the database from ``Data/Documents`` to
    ``Data/Library/Application Support``, so the latter is checked first: when
    both exist, it is the one MoneyWiz is currently writing to.
    """
    home = home or Path.home()
    containers = [
        home / "Library/Containers" / c / "Data" for c in _MONEYWIZ_CONTAINERS
    ]
    return [
        *(c / "Library/Application Support" for c in containers),
        *(c / "Documents" for c in containers),
        home / "Library/Application Support/MoneyWiz",
        home / "Library/Application Support/SilverWiz/MoneyWiz 2",
    ]


def _is_candidate_database(path: Path) -> bool:
    """Return True if ``path`` looks like a usable MoneyWiz database file.

    The suffix check excludes SQLite side files (``-wal``, ``-shm``,
    ``-journal``). The CloudKit shared-scope store (``*_shared.sqlite``) is
    excluded because it has the real schema but no rows, so selecting it
    yields empty results instead of an error.
    """
    if path.suffix.lower() not in _DB_SUFFIXES:
        return False
    if path.stem.lower().endswith("_shared"):
        return False
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError as e:
        logger.debug(f"Skipping {path}: {e.strerror or e}")
        return False


def find_moneywiz_databases(home: Path | None = None) -> list[Path]:
    """Find candidate MoneyWiz databases, best match first.

    Files whose name contains "moneywiz" rank ahead of other SQLite files in
    any searched directory, because the container's ``Application Support``
    directory can also hold unrelated stores. Within each group, results follow
    directory preference and then file name, so the order is deterministic.
    """
    ranked: list[tuple[int, int, str, Path]] = []
    for dir_rank, directory in enumerate(moneywiz_search_dirs(home)):
        if not directory.is_dir():
            continue
        logger.debug(f"Searching for database in: {directory}")
        try:
            entries = list(directory.iterdir())
        except OSError as e:
            # macOS privacy controls can deny access to another app's container
            logger.warning(
                f"Cannot read {directory}: {e.strerror or e}. Grant Full Disk "
                "Access to the app running this server, or set MONEYWIZ_DB_PATH."
            )
            continue
        for path in entries:
            if _is_candidate_database(path):
                name_rank = 0 if "moneywiz" in path.name.lower() else 1
                ranked.append((name_rank, dir_rank, path.name, path))
    return [path for *_, path in sorted(ranked)]


@dataclass
class Config:
    """Server configuration with environment-based defaults."""

    database_path: str
    read_only: bool = True
    cache_ttl: int = 300  # 5 minutes
    max_results: int = 1000
    backup_before_write: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables and .env file.

        Environment Variables:
            MONEYWIZ_DB_PATH: Path to MoneyWiz SQLite database
            MONEYWIZ_READ_ONLY: Enable read-only mode (default: true)
            CACHE_TTL: Cache time-to-live in seconds (default: 300)
            MAX_RESULTS: Maximum query results (default: 1000)
            BACKUP_BEFORE_WRITE: Backup before write operations (default: true)
            LOG_LEVEL: Logging level (default: INFO)

        Returns:
            Configured Config instance

        Raises:
            ValueError: If MoneyWiz database cannot be found
            OSError: If not running on macOS
        """
        # Verify platform first
        if os.name != "posix" or os.uname().sysname != "Darwin":
            raise OSError(
                "MoneyWiz MCP Server only supports macOS. "
                "MoneyWiz is only available on macOS, iOS, and iPadOS."
            )

        # Load environment variables from .env file first
        load_env_file()

        # Get database path from environment or auto-detect
        db_path = os.getenv("MONEYWIZ_DB_PATH")

        if not db_path:
            logger.info("MONEYWIZ_DB_PATH not set, attempting auto-detection...")
            db_path = cls._find_moneywiz_database()

        if not db_path:
            raise ValueError(
                "MoneyWiz database not found. Please:\n"
                "1. Set MONEYWIZ_DB_PATH environment variable, or\n"
                "2. Ensure MoneyWiz is installed and has created a database\n\n"
                "Example: export MONEYWIZ_DB_PATH=/path/to/MoneyWiz.sqlite"
            )

        # Parse other configuration options
        read_only = os.getenv("MONEYWIZ_READ_ONLY", "true").lower() == "true"
        cache_ttl = int(os.getenv("CACHE_TTL", "300"))
        max_results = int(os.getenv("MAX_RESULTS", "1000"))
        backup_before_write = os.getenv("BACKUP_BEFORE_WRITE", "true").lower() == "true"
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        logger.info("Configuration loaded:")
        logger.info(f"  Database: {db_path}")
        logger.info(f"  Read-only: {read_only}")
        logger.info(f"  Cache TTL: {cache_ttl}s")
        logger.info(f"  Max results: {max_results}")

        return cls(
            database_path=db_path,
            read_only=read_only,
            cache_ttl=cache_ttl,
            max_results=max_results,
            backup_before_write=backup_before_write,
            log_level=log_level,
        )

    @classmethod
    def _find_moneywiz_database(cls) -> str | None:
        """Attempt to auto-detect MoneyWiz database location on macOS.

        Searches common MoneyWiz installation locations on macOS only.

        Returns:
            Path to database file if found, None otherwise
        """
        # Verify we're running on macOS
        if os.name != "posix" or os.uname().sysname != "Darwin":
            logger.error("MoneyWiz MCP Server only supports macOS")
            raise OSError(
                "This application only runs on macOS where MoneyWiz is available"
            )

        candidates = find_moneywiz_databases()
        if candidates:
            selected = candidates[0]
            logger.info(f"Found potential MoneyWiz database: {selected}")
            if len(candidates) > 1:
                logger.info(
                    f"{len(candidates) - 1} other candidate database(s) found; "
                    "set MONEYWIZ_DB_PATH to choose a different one"
                )
            return str(selected)

        logger.warning("Could not auto-detect MoneyWiz database location")
        logger.info(
            "Please set MONEYWIZ_DB_PATH environment variable or run setup_env.py"
        )
        return None

    def validate(self) -> bool:
        """Validate configuration settings.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        # Check database file exists
        db_path = Path(self.database_path)
        if not db_path.exists():
            raise ValueError(f"Database file not found: {self.database_path}")

        # Check database file is readable
        if not os.access(self.database_path, os.R_OK):
            raise ValueError(f"Database file not readable: {self.database_path}")

        # Check database file is not empty
        if db_path.stat().st_size == 0:
            raise ValueError(f"Database file is empty: {self.database_path}")

        # Validate numeric settings
        if self.cache_ttl < 0:
            raise ValueError("Cache TTL must be non-negative")

        if self.max_results <= 0:
            raise ValueError("Max results must be positive")

        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_levels:
            raise ValueError(f"Invalid log level: {self.log_level}")

        return True
