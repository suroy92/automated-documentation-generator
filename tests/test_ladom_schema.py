# tests/test_ladom_schema.py

"""
Unit tests for LADOM schema validation and normalization.
"""

import pytest
from src.ladom_schema import LADOMValidator, normalize_ladom


class TestLADOMValidator:
    """Test cases for LADOM validation."""
    
    def test_valid_ladom(self):
        """Test validation of a complete valid LADOM structure."""
        ladom = {
            'project_name': 'Test Project',
            'files': [
                {
                    'path': '/test/file.py',
                    'functions': [
                        {
                            'name': 'test_func',
                            'description': 'Test function',
                            'parameters': [
                                {
                                    'name': 'arg1',
                                    'type': 'str',
                                    'description': 'First argument'
                                }
                            ],
                            'returns': {
                                'type': 'int',
                                'description': 'Return value'
                            }
                        }
                    ],
                    'classes': []
                }
            ]
        }
        
        assert LADOMValidator.validate_ladom(ladom) is True
    
    def test_missing_project_name(self):
        """Test validation fails when project_name is missing."""
        ladom = {
            'files': []
        }
        
        assert LADOMValidator.validate_ladom(ladom) is False
    
    def test_missing_files(self):
        """Test validation fails when files key is missing."""
        ladom = {
            'project_name': 'Test'
        }
        
        assert LADOMValidator.validate_ladom(ladom) is False
    
    def test_invalid_file_structure(self):
        """Test validation fails with invalid file structure."""
        ladom = {
            'project_name': 'Test',
            'files': [
                {
                    # Missing 'path' key
                    'functions': []
                }
            ]
        }
        
        assert LADOMValidator.validate_ladom(ladom) is False
    
    def test_valid_class_structure(self):
        """Test validation of class structure."""
        ladom = {
            'project_name': 'Test',
            'files': [
                {
                    'path': '/test/file.py',
                    'functions': [],
                    'classes': [
                        {
                            'name': 'TestClass',
                            'description': 'Test class',
                            'methods': [
                                {
                                    'name': 'method1',
                                    'description': 'Test method',
                                    'parameters': [],
                                    'returns': {
                                        'type': 'void',
                                        'description': ''
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assert LADOMValidator.validate_ladom(ladom) is True


class TestNormalizeLADOM:
    """Test cases for LADOM normalization."""
    
    def test_normalize_minimal_ladom(self):
        """Test normalization fills in missing fields."""
        minimal_ladom = {
            'files': [
                {
                    'functions': [
                        {
                            'name': 'func'
                        }
                    ]
                }
            ]
        }
        
        normalized = normalize_ladom(minimal_ladom)
        
        assert 'project_name' in normalized
        assert normalized['project_name'] == 'Unnamed Project'
        assert len(normalized['files']) == 1
        assert normalized['files'][0]['functions'][0]['description'] == 'No description provided.'
    
    def test_normalize_parameters(self):
        """Test normalization of parameters."""
        ladom = {
            'project_name': 'Test',
            'files': [
                {
                    'path': '/test/file.py',
                    'functions': [
                        {
                            'name': 'func',
                            'parameters': [
                                {'name': 'arg1'}  # Missing type and description
                            ]
                        }
                    ],
                    'classes': []
                }
            ]
        }
        
        normalized = normalize_ladom(ladom)
        param = normalized['files'][0]['functions'][0]['parameters'][0]
        
        assert param['type'] == 'any'
        assert param['description'] == 'No description available.'
    
    def test_normalize_returns(self):
        """Test normalization of returns."""
        ladom = {
            'project_name': 'Test',
            'files': [
                {
                    'path': '/test/file.py',
                    'functions': [
                        {
                            'name': 'func',
                            'parameters': []
                            # Missing returns
                        }
                    ],
                    'classes': []
                }
            ]
        }
        
        normalized = normalize_ladom(ladom)
        returns = normalized['files'][0]['functions'][0]['returns']
        
        assert returns['type'] == 'void'
        assert 'description' in returns