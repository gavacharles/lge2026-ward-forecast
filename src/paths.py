"""Shared paths.

Bulk IEC data (~1 GB) lives outside OneDrive because on-demand sync evicts large files
and reads then time out. Override with the ELECTION_DATA environment variable.
"""
import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("ELECTION_DATA", Path.home() / "ElectionModelData"))
RAW = DATA / "raw"
INTERIM = DATA / "interim"
OUTPUTS = PROJECT / "outputs"
CONFIG = PROJECT / "config"
