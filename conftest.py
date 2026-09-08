"""Root conftest: ensure the repo root is importable so tests can do
`from core.interfaces import ...` etc. regardless of pytest's rootdir/sys.path
insertion behavior (fixes CI "ModuleNotFoundError: No module named 'core'").
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
