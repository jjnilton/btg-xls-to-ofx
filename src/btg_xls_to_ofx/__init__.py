"""Convert BTG Pactual checking account statements (.xls/.xlsx) to OFX."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("btg-xls-to-ofx")
except PackageNotFoundError:  # uninstalled source checkout: degrade, don't crash import
    __version__ = "0.0.0+unknown"
