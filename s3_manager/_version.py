"""
SkyCLI version management module
"""

__version__ = "0.4.3"


def get_version():
    """Get the current version string"""
    return __version__


def get_version_info():
    """Get the version info dictionary by parsing __version__"""
    parts = __version__.split('.')
    return {
        "major": int(parts[0]),
        "minor": int(parts[1]),
        "patch": int(parts[2]) if len(parts) > 2 else 0,
        "release": True
    }
