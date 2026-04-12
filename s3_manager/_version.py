"""
SkyCLI version management module
"""

__version__ = "0.2.2"
VERSION_INFO = {
    "major": 0,
    "minor": 2,
    "patch": 2,
    "release": True
}


def get_version():
    """Get the current version string"""
    return __version__


def get_version_info():
    """Get the version info dictionary"""
    return VERSION_INFO
