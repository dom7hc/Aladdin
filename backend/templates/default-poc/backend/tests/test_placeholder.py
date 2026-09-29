"""Baseline suite for the generated PoC backend.

The Developer Agent extends these tests alongside the code it generates; the
AI PoC Builder tester runs them with pytest after compiling the backend.
"""

from main import app


def test_health_route_is_defined():
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/health" in paths
