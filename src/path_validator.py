# src/path_validator.py

"""
Path validation and security checks.
"""

import os
import logging
from typing import List

logger = logging.getLogger(__name__)


class PathValidator:
    """Validates and sanitizes file paths for security."""
    
    def __init__(self, forbidden_paths: List[str] = None):
        """
        Initialize the path validator.
        
        Args:
            forbidden_paths: List of forbidden directory paths
        """
        self.forbidden_paths = forbidden_paths or [
            '/etc', '/sys', '/proc', '/root',
            os.path.expanduser('~/.ssh'),
            '/var/log', '/boot'
        ]
        
        # Normalize forbidden paths
        self.forbidden_paths = [os.path.abspath(os.path.expanduser(p)) 
                               for p in self.forbidden_paths]
    
    def is_safe_path(self, path: str) -> bool:
        """
        Check if a path is safe to access.
        
        Args:
            path: Path to validate
            
        Returns:
            True if path is safe, False otherwise
        """
        try:
            original_path = path
            
            # STRICT: Reject ANY path with traversal patterns immediately
            if '..' in path or '../' in path or '..\\' in path or '%2e%2e' in path.lower():
                logger.error(f"Path traversal detected and rejected: {original_path}")
                return False
            
            # Get absolute path
            abs_path = os.path.abspath(os.path.expanduser(path))
            
            # Check if path exists
            if not os.path.exists(abs_path):
                logger.warning(f"Path does not exist: {original_path}")
                return False
            
            # Resolve symlinks to prevent symlink-based attacks
            real_path = os.path.realpath(abs_path)
            
            # Check against forbidden paths (use both abs_path and real_path)
            for forbidden in self.forbidden_paths:
                if abs_path.startswith(forbidden) or real_path.startswith(forbidden):
                    logger.error(f"Access denied to forbidden path: {original_path}")
                    return False
            
            # Ensure resolved path doesn't escape its parent through symlinks
            real_parent = os.path.dirname(real_path) or os.path.dirname(abs_path)
            if real_parent:
                try:
                    common = os.path.commonpath([abs_path, real_path])
                    if not common.startswith(real_parent) and real_path != abs_path:
                        logger.error(f"Symlink traversal detected and rejected: {original_path}")
                        return False
                except (ValueError, OSError):
                    logger.error(f"Invalid path comparison for: {original_path}")
                    return False
            
            return True
            
        except (OSError, ValueError) as e:
            logger.error(f"Error validating path {path}: {e}")
            return False
    
    def validate_project_path(self, path: str) -> bool:
        """
        Validate a project directory path.
        
        Args:
            path: Project path to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not os.path.isdir(path):
            logger.error(f"Not a valid directory: {path}")
            return False
        
        return self.is_safe_path(path)
    
    def get_safe_output_path(self, base_dir: str, project_name: str) -> str:
        """
        Generate a safe output path for documentation.
        
        Args:
            base_dir: Base documentation directory
            project_name: Project name
            
        Returns:
            Safe output directory path
        """
        # Sanitize project name
        safe_name = "".join(c for c in project_name 
                           if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        
        output_path = os.path.join(base_dir, safe_name)
        return os.path.abspath(output_path)