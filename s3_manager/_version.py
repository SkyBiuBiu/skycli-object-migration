"""
SkyCLI version management module
"""

__version__ = "0.3.0"
VERSION_INFO = {
    "major": 0,
    "minor": 3,
    "patch": 0,
    "release": True
}


def get_version():
    """Get the current version string"""
    return __version__


def get_version_info():
    """Get the version info dictionary"""
    return VERSION_INFO
