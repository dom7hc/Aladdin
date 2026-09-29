"""Pytest bootstrap for the generated PoC backend.

Makes template modules (e.g. ``main``) importable when pytest runs from this
directory without installing the PoC as a package.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
