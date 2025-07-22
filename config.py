"""
Configuration management for Auto-Snap MCP.
Centralized settings with environment variable support.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AutoSnapConfig:
    """Centralized configuration manager with environment variable support."""
    
    def __init__(self):
        """Initialize configuration with environment variable defaults."""
        self._config = self._load_config()
        self._ensure_directories()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables with fallback defaults."""
        # Get user home directory for default paths
        home_dir = Path.home()
        
        # Directory configuration
        default_output_dir = home_dir / "auto-snap-captures"
        default_temp_dir = Path(tempfile.gettempdir()) / "auto-snap-temp"
        
        config = {
            # Directory settings
            "output_dir": Path(os.getenv("AUTO_SNAP_OUTPUT_DIR", default_output_dir)),
            "temp_dir": Path(os.getenv("AUTO_SNAP_TEMP_DIR", default_temp_dir)),
            "use_date_subdirs": os.getenv("AUTO_SNAP_USE_DATE_SUBDIRS", "false").lower() == "true",
            "use_session_subdirs": os.getenv("AUTO_SNAP_USE_SESSION_SUBDIRS", "false").lower() == "true",
            
            # File naming configuration
            "file_name_template": os.getenv("AUTO_SNAP_FILE_NAME_TEMPLATE", "page_{page:03d}"),
            "timestamp_format": os.getenv("AUTO_SNAP_TIMESTAMP_FORMAT", "iso"),  # iso, unix, custom
            "custom_timestamp_pattern": os.getenv("AUTO_SNAP_CUSTOM_TIMESTAMP", "%Y%m%d_%H%M%S"),
            "include_timestamp": os.getenv("AUTO_SNAP_INCLUDE_TIMESTAMP", "false").lower() == "true",
            
            # Output format settings
            "image_format": os.getenv("AUTO_SNAP_IMAGE_FORMAT", "png").lower(),
            "image_quality": int(os.getenv("AUTO_SNAP_IMAGE_QUALITY", "95")),
            "pdf_compression": os.getenv("AUTO_SNAP_PDF_COMPRESSION", "true").lower() == "true",
            
            # Session management
            "session_id": os.getenv("AUTO_SNAP_SESSION_ID", None),
            "project_name": os.getenv("AUTO_SNAP_PROJECT_NAME", None),
            
            # Cleanup policies
            "auto_cleanup_temp": os.getenv("AUTO_SNAP_AUTO_CLEANUP_TEMP", "true").lower() == "true",
            "temp_retention_hours": int(os.getenv("AUTO_SNAP_TEMP_RETENTION_HOURS", "24")),
            "max_temp_files": int(os.getenv("AUTO_SNAP_MAX_TEMP_FILES", "1000")),
            
            # Legacy compatibility
            "legacy_mode": os.getenv("AUTO_SNAP_LEGACY_MODE", "true").lower() == "true",
        }
        
        logger.info(f"Loaded configuration: output_dir={config['output_dir']}, temp_dir={config['temp_dir']}")
        return config
    
    def _ensure_directories(self):
        """Ensure that configured directories exist."""
        try:
            self._config["output_dir"].mkdir(parents=True, exist_ok=True)
            self._config["temp_dir"].mkdir(parents=True, exist_ok=True)
            logger.info("Configuration directories created successfully")
        except Exception as e:
            logger.warning(f"Could not create configuration directories: {e}")
    
    def get_output_dir(self, custom_dir: Optional[str] = None) -> Path:
        """
        Get the output directory, with optional custom override.
        
        Args:
            custom_dir: Custom directory to use instead of default
            
        Returns:
            Path object for the output directory
        """
        if custom_dir:
            # User provided custom directory - use as-is for backward compatibility
            return Path(custom_dir)
        
        base_dir = self._config["output_dir"]
        
        # Add subdirectories based on configuration
        if self._config["use_date_subdirs"]:
            date_subdir = datetime.now().strftime("%Y-%m-%d")
            base_dir = base_dir / date_subdir
        
        if self._config["use_session_subdirs"] and self._config["session_id"]:
            base_dir = base_dir / self._config["session_id"]
        
        if self._config["project_name"]:
            base_dir = base_dir / self._config["project_name"]
        
        # Ensure directory exists
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir
    
    def get_temp_dir(self, custom_dir: Optional[str] = None) -> Path:
        """
        Get the temporary directory, with optional custom override.
        
        Args:
            custom_dir: Custom directory to use instead of default
            
        Returns:
            Path object for the temp directory
        """
        if custom_dir:
            return Path(custom_dir)
        
        temp_dir = self._config["temp_dir"]
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    
    def generate_filename(self, 
                         page_number: int = 1, 
                         base_name: Optional[str] = None,
                         extension: Optional[str] = None) -> str:
        """
        Generate a filename based on configuration template.
        
        Args:
            page_number: Page number for multi-page documents
            base_name: Override base name (e.g., from window title)
            extension: File extension (defaults to configured image format)
            
        Returns:
            Generated filename string
        """
        if extension is None:
            extension = self._config["image_format"]
        
        # Start with base template
        template = self._config["file_name_template"]
        filename = template.format(page=page_number)
        
        # Add timestamp if configured
        if self._config["include_timestamp"]:
            timestamp = self._generate_timestamp()
            filename = f"{filename}_{timestamp}"
        
        # Add base name if provided (useful for window titles)
        if base_name:
            # Sanitize base name for filesystem
            safe_base_name = self._sanitize_filename(base_name)
            filename = f"{safe_base_name}_{filename}"
        
        return f"{filename}.{extension}"
    
    def _generate_timestamp(self) -> str:
        """Generate timestamp based on configured format."""
        now = datetime.now()
        
        if self._config["timestamp_format"] == "unix":
            return str(int(now.timestamp()))
        elif self._config["timestamp_format"] == "custom":
            return now.strftime(self._config["custom_timestamp_pattern"])
        else:  # Default to ISO format
            return now.strftime("%Y%m%d_%H%M%S")
    
    def _sanitize_filename(self, filename: str, max_length: int = 50) -> str:
        """
        Sanitize filename by removing invalid characters and limiting length.
        
        Args:
            filename: Original filename
            max_length: Maximum allowed length
            
        Returns:
            Sanitized filename
        """
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        sanitized = ''.join(c for c in filename if c not in invalid_chars)
        
        # Replace spaces with underscores
        sanitized = sanitized.replace(' ', '_')
        
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip('_')
    
    def get_legacy_defaults(self) -> Dict[str, str]:
        """
        Get legacy default directory names for backward compatibility.
        
        Returns:
            Dictionary with legacy directory names
        """
        return {
            "captures": "captures",
            "temp_captures": "temp_captures"
        }
    
    def should_use_legacy_mode(self) -> bool:
        """Check if legacy mode is enabled for backward compatibility."""
        return self._config["legacy_mode"]
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration for debugging."""
        return {
            "output_dir": str(self._config["output_dir"]),
            "temp_dir": str(self._config["temp_dir"]),
            "image_format": self._config["image_format"],
            "file_name_template": self._config["file_name_template"],
            "timestamp_format": self._config["timestamp_format"],
            "use_date_subdirs": self._config["use_date_subdirs"],
            "use_session_subdirs": self._config["use_session_subdirs"],
            "legacy_mode": self._config["legacy_mode"],
        }


# Global configuration instance
_config_instance: Optional[AutoSnapConfig] = None


def get_config() -> AutoSnapConfig:
    """Get the global configuration instance (singleton pattern)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = AutoSnapConfig()
    return _config_instance


def reload_config() -> AutoSnapConfig:
    """Reload configuration from environment variables."""
    global _config_instance
    _config_instance = AutoSnapConfig()
    return _config_instance


# Convenience functions for common operations
def get_output_directory(custom_dir: Optional[str] = None) -> Path:
    """Get configured output directory."""
    return get_config().get_output_dir(custom_dir)


def get_temp_directory(custom_dir: Optional[str] = None) -> Path:
    """Get configured temporary directory."""
    return get_config().get_temp_dir(custom_dir)


def generate_page_filename(page_number: int = 1, 
                          base_name: Optional[str] = None,
                          extension: Optional[str] = None) -> str:
    """Generate a page filename using current configuration."""
    return get_config().generate_filename(page_number, base_name, extension)