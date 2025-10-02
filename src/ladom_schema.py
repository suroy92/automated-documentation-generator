# src/ladom_schema.py

"""
Language-Agnostic Document Object Model (LADOM) Schema Definition.
This module defines the standardized structure for representing code documentation
across different programming languages.
"""

from typing import TypedDict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class Parameter(TypedDict, total=False):
    """Represents a function/method parameter."""
    name: str
    type: str
    description: str


class Returns(TypedDict, total=False):
    """Represents a function/method return value."""
    type: str
    description: str


class Function(TypedDict, total=False):
    """Represents a function or standalone method."""
    name: str
    description: str
    parameters: List[Parameter]
    returns: Returns


class Method(TypedDict, total=False):
    """Represents a class method."""
    name: str
    description: str
    parameters: List[Parameter]
    returns: Returns


class Class(TypedDict, total=False):
    """Represents a class definition."""
    name: str
    description: str
    methods: List[Method]


class File(TypedDict, total=False):
    """Represents a source file."""
    path: str
    functions: List[Function]
    classes: List[Class]


class LADOM(TypedDict, total=False):
    """Complete LADOM structure for a project."""
    project_name: str
    files: List[File]


class LADOMValidator:
    """Validates LADOM structures for compliance with the schema."""
    
    @staticmethod
    def validate_parameter(param: dict) -> bool:
        """Validates a parameter structure."""
        if not isinstance(param, dict):
            logger.error("Parameter must be a dictionary")
            return False
        
        required_keys = {'name', 'type', 'description'}
        if not required_keys.issubset(param.keys()):
            missing = required_keys - param.keys()
            logger.warning(f"Parameter missing keys: {missing}")
            # Allow missing type as it can be 'any'
            if 'name' not in param:
                return False
        
        return True
    
    @staticmethod
    def validate_returns(returns: dict) -> bool:
        """Validates a returns structure."""
        if not isinstance(returns, dict):
            logger.error("Returns must be a dictionary")
            return False
        
        if 'type' not in returns and 'description' not in returns:
            logger.warning("Returns should have at least 'type' or 'description'")
            return False
        
        return True
    
    @staticmethod
    def validate_function(func: dict) -> bool:
        """Validates a function structure."""
        if not isinstance(func, dict):
            logger.error("Function must be a dictionary")
            return False
        
        if 'name' not in func:
            logger.error("Function must have a 'name' field")
            return False
        
        if 'parameters' in func:
            if not isinstance(func['parameters'], list):
                logger.error("Function parameters must be a list")
                return False
            
            for param in func['parameters']:
                if not LADOMValidator.validate_parameter(param):
                    return False
        
        if 'returns' in func:
            if not LADOMValidator.validate_returns(func['returns']):
                return False
        
        return True
    
    @staticmethod
    def validate_method(method: dict) -> bool:
        """Validates a method structure (same as function)."""
        return LADOMValidator.validate_function(method)
    
    @staticmethod
    def validate_class(cls: dict) -> bool:
        """Validates a class structure."""
        if not isinstance(cls, dict):
            logger.error("Class must be a dictionary")
            return False
        
        if 'name' not in cls:
            logger.error("Class must have a 'name' field")
            return False
        
        if 'methods' in cls:
            if not isinstance(cls['methods'], list):
                logger.error("Class methods must be a list")
                return False
            
            for method in cls['methods']:
                if not LADOMValidator.validate_method(method):
                    return False
        
        return True
    
    @staticmethod
    def validate_file(file: dict) -> bool:
        """Validates a file structure."""
        if not isinstance(file, dict):
            logger.error("File must be a dictionary")
            return False
        
        if 'path' not in file:
            logger.error("File must have a 'path' field")
            return False
        
        if 'functions' in file:
            if not isinstance(file['functions'], list):
                logger.error("File functions must be a list")
                return False
            
            for func in file['functions']:
                if not LADOMValidator.validate_function(func):
                    logger.warning(f"Invalid function in {file.get('path', 'unknown')}")
        
        if 'classes' in file:
            if not isinstance(file['classes'], list):
                logger.error("File classes must be a list")
                return False
            
            for cls in file['classes']:
                if not LADOMValidator.validate_class(cls):
                    logger.warning(f"Invalid class in {file.get('path', 'unknown')}")
        
        return True
    
    @staticmethod
    def validate_ladom(ladom: dict) -> bool:
        """Validates the complete LADOM structure."""
        if not isinstance(ladom, dict):
            logger.error("LADOM must be a dictionary")
            return False
        
        required_keys = {'project_name', 'files'}
        if not required_keys.issubset(ladom.keys()):
            missing = required_keys - ladom.keys()
            logger.error(f"LADOM missing required keys: {missing}")
            return False
        
        if not isinstance(ladom['files'], list):
            logger.error("LADOM files must be a list")
            return False
        
        for file in ladom['files']:
            if not LADOMValidator.validate_file(file):
                logger.error(f"Invalid file structure in LADOM")
                return False
        
        logger.debug("LADOM structure validated successfully")
        return True


def normalize_ladom(ladom: dict) -> dict:
    """
    Normalizes a LADOM structure, filling in missing fields with defaults.
    
    Args:
        ladom: The LADOM structure to normalize
        
    Returns:
        A normalized LADOM structure with all optional fields filled
    """
    normalized = {
        'project_name': ladom.get('project_name', 'Unnamed Project'),
        'files': []
    }
    
    for file in ladom.get('files', []):
        normalized_file = {
            'path': file.get('path', 'unknown'),
            'functions': [],
            'classes': []
        }
        
        # Normalize functions
        for func in file.get('functions', []):
            normalized_func = {
                'name': func.get('name', 'unnamed'),
                'description': func.get('description', 'No description provided.'),
                'parameters': [],
                'returns': func.get('returns', {'type': 'void', 'description': 'No return value.'})
            }
            
            for param in func.get('parameters', []):
                normalized_param = {
                    'name': param.get('name', 'unnamed'),
                    'type': param.get('type', 'any'),
                    'description': param.get('description', 'No description available.')
                }
                normalized_func['parameters'].append(normalized_param)
            
            normalized_file['functions'].append(normalized_func)
        
        # Normalize classes
        for cls in file.get('classes', []):
            normalized_class = {
                'name': cls.get('name', 'UnnamedClass'),
                'description': cls.get('description', 'No description provided.'),
                'methods': []
            }
            
            for method in cls.get('methods', []):
                normalized_method = {
                    'name': method.get('name', 'unnamed'),
                    'description': method.get('description', 'No description provided.'),
                    'parameters': [],
                    'returns': method.get('returns', {'type': 'void', 'description': 'No return value.'})
                }
                
                for param in method.get('parameters', []):
                    normalized_param = {
                        'name': param.get('name', 'unnamed'),
                        'type': param.get('type', 'any'),
                        'description': param.get('description', 'No description available.')
                    }
                    normalized_method['parameters'].append(normalized_param)
                
                normalized_class['methods'].append(normalized_method)
            
            normalized_file['classes'].append(normalized_class)
        
        normalized['files'].append(normalized_file)
    
    return normalized