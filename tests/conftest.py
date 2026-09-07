"""Isolate temp campaigns across Windows users and sandboxed test runners."""
import tempfile
import uuid
from pathlib import Path


def pytest_configure(config):
    if config.option.basetemp is None:
        # A fresh directory avoids permission collisions in pytest-of-<user>.
        # Honor an explicit --basetemp chosen by the developer.
        config.option.basetemp = str(Path(tempfile.gettempdir()) / f"empire-manager-tests-{uuid.uuid4().hex}")
