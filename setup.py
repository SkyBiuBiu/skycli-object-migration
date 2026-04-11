from setuptools import setup, find_packages

setup(
    name="skycli",
    version="0.2.0",
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
