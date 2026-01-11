# src/config_loader.py

"""
Configuration loader for the documentation generator.
Loads settings from config.yaml and environment variables with validation.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


CONFIG_SCHEMA = {
    'exclude_dirs': list,
    'output': dict,
    'llm': dict,
    'cache': dict,
    'logging': dict,
    'processing': dict,
    'security': dict,
}

OUTPUT_SCHEMA = {
    'directory': str,
    'format': str,
    'include_toc': bool,
}

LLM_SCHEMA = {
    'provider': str,
    'base_url': str,
    'model': str,
    'temperature': (int, float),
    'rate_limit_calls_per_minute': int,
    'timeout': int,
    'embedding_model': (str, type(None)),
}

CACHE_SCHEMA = {
    'enabled': bool,
    'file': str,
}

LOGGING_SCHEMA = {
    'level': str,
    'format': str,
    'file': str,
}

PROCESSING_SCHEMA = {
    'parallel': bool,
    'max_workers': int,
}

SECURITY_SCHEMA = {
    'forbidden_paths': list,
    'validate_paths': bool,
}


class ConfigurationValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


def _validate_type(value: Any, expected_type: type, field_path: str) -> None:
    """Validate a configuration value matches expected type."""
    if expected_type is type(None):
        # Any value is acceptable
        return

    if not isinstance(value, expected_type):
        raise ConfigurationValidationError(
            f"Configuration field '{field_path}' should be {expected_type.__name__}, got {type(value).__name__}"
        )


def _validate_range(value: int, min_val: int, max_val: Optional[int], field_path: str) -> None:
    """Validate a configuration value is within expected range."""
    if value < min_val:
        raise ConfigurationValidationError(
            f"Configuration field '{field_path}' must be >= {min_val}, got {value}"
        )
    if max_val is not None and value > max_val:
        raise ConfigurationValidationError(
            f"Configuration field '{field_path}' must be <= {max_val}, got {value}"
        )


def _validate_choice(value: str, choices: list, field_path: str) -> None:
    """Validate a configuration value matches one of the allowed choices."""
    if value not in choices:
        raise ConfigurationValidationError(
            f"Configuration field '{field_path}' must be one of {choices}, got '{value}'"
        )


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
        Load configuration from file with validation.

        Returns:
            Validated configuration dictionary
        """
        config = self.DEFAULT_CONFIG.copy()

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        self._validate_config(user_config)
                        config = self._merge_configs(config, user_config)
                        logger.info(f"Loaded configuration from {self.config_path}")
            except yaml.YAMLError as e:
                logger.error(f"Invalid YAML syntax in {self.config_path}: {e}")
                raise ConfigurationValidationError(f"Invalid YAML configuration: {e}") from e
            except ConfigurationValidationError as e:
                logger.error(f"Configuration validation failed: {e}")
                raise
            except (OSError, IOError) as e:
                logger.warning(f"Failed to load config from {self.config_path}: {e}")
                logger.info("Using default configuration")
        else:
            logger.info(f"Config file not found at {self.config_path}, using defaults")

        return config

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration values against schema."""
        # Validate top-level structure
        for key in config.keys():
            if key not in CONFIG_SCHEMA:
                logger.warning(f"Unknown configuration key: '{key}'")

        # Validate logging settings
        if 'logging' in config:
            logging_cfg = config['logging']
            if 'level' in logging_cfg:
                _validate_choice(
                    logging_cfg['level'].upper(),
                    ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                    'logging.level'
                )
            if 'format' in logging_cfg:
                _validate_type(logging_cfg['format'], str, 'logging.format')

        # Validate LLM settings
        if 'llm' in config:
            llm_cfg = config['llm']
            if 'temperature' in llm_cfg:
                _validate_range(float(llm_cfg['temperature']), 0.0, 2.0, 'llm.temperature')
            if 'timeout' in llm_cfg:
                _validate_range(llm_cfg['timeout'], 10, 600, 'llm.timeout')
            if 'rate_limit_calls_per_minute' in llm_cfg:
                _validate_range(llm_cfg['rate_limit_calls_per_minute'], 1, 120, 'llm.rate_limit_calls_per_minute')

        # Validate processing settings
        if 'processing' in config:
            proc_cfg = config['processing']
            if 'max_workers' in proc_cfg:
                _validate_range(proc_cfg['max_workers'], 1, 32, 'processing.max_workers')

        # Validate cache settings
        if 'cache' in config:
            cache_cfg = config['cache']
            if 'file' in cache_cfg:
                # Ensure cache file path is valid (allow both absolute and relative paths)
                cache_file = cache_cfg['file']
                # Just validate it's a non-empty string, paths are resolved later
                if not cache_file or not isinstance(cache_file, str):
                    raise ConfigurationValidationError(
                        f"Cache file path must be a non-empty string: '{cache_file}'"
                    )
    
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