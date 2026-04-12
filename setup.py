from setuptools import setup, find_packages
import os
import re

def get_version():
    """Read version from _version.py without importing the package"""
    version_file = os.path.join(os.path.dirname(__file__), "s3_manager", "_version.py")
    with open(version_file, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'^__version__ = ["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            return match.group(1)
    raise RuntimeError("Unable to find version string")

setup(
    name="skycli",
    version=get_version(),
    description="S3 Compatible Object Storage Manager and Migration Tool",
    author="SkyCLI",
    packages=find_packages(),
    install_requires=[
        "boto3>=1.26.0",
        "PyYAML>=6.0",
        "python-dateutil>=2.8.0",
        "watchdog>=3.0.0",
    ],
    extras_require={
        "test": [
            "pytest>=7.0.0",
            "pytest-mock>=3.10.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "skycli=s3_manager.skycli:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
