"""Configuration management for MoneyWiz MCP Server."""

import os
import logging
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables.
        
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
        """
        # Get database path from environment or auto-detect
        db_path = os.getenv('MONEYWIZ_DB_PATH')
        
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
        read_only = os.getenv('MONEYWIZ_READ_ONLY', 'true').lower() == 'true'
        cache_ttl = int(os.getenv('CACHE_TTL', '300'))
        max_results = int(os.getenv('MAX_RESULTS', '1000'))
        backup_before_write = os.getenv('BACKUP_BEFORE_WRITE', 'true').lower() == 'true'
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        
        logger.info(f"Configuration loaded:")
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
            log_level=log_level
        )
    
    @classmethod
    def _find_moneywiz_database(cls) -> Optional[str]:
        """Attempt to auto-detect MoneyWiz database location.
        
        Searches common MoneyWiz installation locations on different platforms.
        
        Returns:
            Path to database file if found, None otherwise
        """
        possible_paths = []
        
        # macOS locations
        if os.name == 'posix' and os.uname().sysname == 'Darwin':
            home = Path.home()
            possible_paths.extend([
                # MoneyWiz 3 locations
                home / "Library/Containers/com.moneywiz.mac/Data/Documents",
                home / "Library/Containers/com.moneywiz.personalfinance/Data/Documents",
                home / "Library/Application Support/MoneyWiz",
                # MoneyWiz 2 locations  
                home / "Library/Application Support/SilverWiz/MoneyWiz 2",
                # Common user locations
                home / "Documents/MoneyWiz",
                home / "Desktop/MoneyWiz",
            ])
        
        # Windows locations
        elif os.name == 'nt':
            home = Path.home()
            possible_paths.extend([
                home / "AppData/Local/SilverWiz/MoneyWiz",
                home / "AppData/Roaming/SilverWiz/MoneyWiz",
                home / "Documents/MoneyWiz",
                home / "Desktop/MoneyWiz",
            ])
        
        # Linux locations
        else:
            home = Path.home()
            possible_paths.extend([
                home / ".config/MoneyWiz",
                home / ".local/share/MoneyWiz",
                home / "Documents/MoneyWiz",
                home / "Desktop/MoneyWiz",
            ])
        
        # Search for SQLite database files
        for base_path in possible_paths:
            if not base_path.exists():
                continue
                
            logger.debug(f"Searching for database in: {base_path}")
            
            # Look for common database file patterns
            patterns = [
                "*.sqlite",
                "*.sqlite3", 
                "*.db",
                "*MoneyWiz*.sqlite*",
                "*database*.sqlite*"
            ]
            
            for pattern in patterns:
                for db_file in base_path.glob(pattern):
                    if db_file.is_file() and db_file.stat().st_size > 0:
                        logger.info(f"Found potential MoneyWiz database: {db_file}")
                        return str(db_file)
        
        # Also check current directory and common locations
        current_dir = Path.cwd()
        for pattern in ["*.sqlite", "*.sqlite3", "MoneyWiz*.db"]:
            for db_file in current_dir.glob(pattern):
                if db_file.is_file():
                    logger.info(f"Found database in current directory: {db_file}")
                    return str(db_file)
        
        logger.warning("Could not auto-detect MoneyWiz database location")
        return None
    
    def validate(self) -> bool:
        """Validate configuration settings.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Check database file exists
        if not os.path.exists(self.database_path):
            raise ValueError(f"Database file not found: {self.database_path}")
        
        # Check database file is readable
        if not os.access(self.database_path, os.R_OK):
            raise ValueError(f"Database file not readable: {self.database_path}")
        
        # Check database file is not empty
        if os.path.getsize(self.database_path) == 0:
            raise ValueError(f"Database file is empty: {self.database_path}")
        
        # Validate numeric settings
        if self.cache_ttl < 0:
            raise ValueError("Cache TTL must be non-negative")
        
        if self.max_results <= 0:
            raise ValueError("Max results must be positive")
        
        # Validate log level
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level not in valid_levels:
            raise ValueError(f"Invalid log level: {self.log_level}")
        
        return True