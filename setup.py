# setup.py

"""
Setup configuration for the Automated Documentation Generator.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="automated-doc-generator",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="AI-powered automated documentation generator for multi-language projects",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/automated-doc-generator",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Documentation",
        "Topic :: Software Development :: Code Generators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "docgen=src.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.md"],
    },
)