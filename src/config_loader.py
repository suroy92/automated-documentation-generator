# src/config_loader.py

"""
Configuration loader for the documentation generator.
Loads settings from config.yaml and environment variables.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Loads and manages configuration settings."""
    
    DEFAULT_CONFIG = {
        'exclude_dirs': [
            'node_modules', '__pycache__', '.git', '.venv', 'venv',
            'dist', 'build', '.vscode', '.idea', '.pytest_cache'
        ],
        'output': {
            'directory': 'Documentation',
            'format': 'markdown',
            'include_toc': True
        },
        'llm': {
            'provider': 'ollama',
            'base_url': 'http://localhost:11434',
            'model': 'qwen2.5-coder:7b',
            'temperature': 0.2,
            'rate_limit_calls_per_minute': 20,
            'timeout': 120,
            'embedding_model': 'all-minilm:l6-v2'
        },
        'cache': {
            'enabled': True,
            'file': '.docstring_cache.json'
        },
        'logging': {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'file': 'docgen.log'
        },
        'processing': {
            'parallel': True,
            'max_workers': 4
        },
        'security': {
            'forbidden_paths': ['/etc', '/sys', '/proc', '~/.ssh'],
            'validate_paths': True
        }
    }
    
    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize the configuration loader.
        
        Args:
            config_path: Path to the configuration YAML file
        """
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or use defaults.
        
        Returns:
            Configuration dictionary
        """
        config = self.DEFAULT_CONFIG.copy()
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        config = self._merge_configs(config, user_config)
                        logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config from {self.config_path}: {e}")
                logger.info("Using default configuration")
        else:
            logger.info(f"Config file not found at {self.config_path}, using defaults")
        
        return config
    
    def _merge_configs(self, default: Dict, user: Dict) -> Dict:
        """
        Recursively merge user config into default config.
        
        Args:
            default: Default configuration
            user: User configuration
            
        Returns:
            Merged configuration
        """
        merged = default.copy()
        
        for key, value in user.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        
        return merged
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'llm.model')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_exclude_dirs(self) -> List[str]:
        """Get list of directories to exclude from scanning."""
        return self.config.get('exclude_dirs', [])
    
    def get_output_dir(self) -> str:
        """Get output directory path."""
        return self.config.get('output', {}).get('directory', 'Documentation')
    
    def get_llm_model(self) -> str:
        """Get LLM model name."""
        return self.config.get('llm', {}).get('model', 'gemini-2.5-flash')
    
    def get_llm_temperature(self) -> float:
        """Get LLM temperature setting."""
        return self.config.get('llm', {}).get('temperature', 0.3)
    
    def get_max_retries(self) -> int:
        """Get maximum retry attempts for LLM calls."""
        return self.config.get('llm', {}).get('max_retries', 3)
    
    def get_rate_limit(self) -> int:
        """Get rate limit for LLM calls per minute."""
        return self.config.get('llm', {}).get('rate_limit_calls_per_minute', 20)
    
    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.config.get('cache', {}).get('enabled', True)
    
    def get_cache_file(self) -> str:
        """Get cache file path."""
        return self.config.get('cache', {}).get('file', '.docstring_cache.json')
    
    def get_log_level(self) -> str:
        """Get logging level."""
        return self.config.get('logging', {}).get('level', 'INFO')
    
    def get_log_format(self) -> str:
        """Get logging format string."""
        return self.config.get('logging', {}).get('format', '%(levelname)s - %(message)s')
    
    def get_log_file(self) -> str:
        """Get log file path."""
        return self.config.get('logging', {}).get('file', 'docgen.log')
    
    def is_parallel_processing(self) -> bool:
        """Check if parallel processing is enabled."""
        return self.config.get('processing', {}).get('parallel', True)
    
    def get_max_workers(self) -> int:
        """Get maximum number of worker threads."""
        return self.config.get('processing', {}).get('max_workers', 4)
    
    def get_forbidden_paths(self) -> List[str]:
        """Get list of forbidden paths."""
        forbidden = self.config.get('security', {}).get('forbidden_paths', [])
        # Expand user paths
        return [os.path.expanduser(path) for path in forbidden]
    
    def should_validate_paths(self) -> bool:
        """Check if path validation is enabled."""
        return self.config.get('security', {}).get('validate_paths', True)