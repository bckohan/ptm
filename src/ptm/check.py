import os
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path

from dotenv import dotenv_values
from packaging.requirements import Requirement


def validate_environment():
    # todo - more reliable check
    python_actual = sys.version.split()[0]
    python_expected = os.environ["PTM_PYTHON"]
    assert python_actual.startswith(python_expected), (
        f"Unexpected python version {python_actual} != {python_expected}"
    )
    for req in os.environ["PTM_CONSTRAINTS"].split(";"):
        req = Requirement(req)
        if req.specifier:
            assert pkg_version(req.name) in req.specifier, (
                f"Unexpected package version {req} != {pkg_version(req.name)}"
            )

    for key, value in dotenv_values(Path(os.environ["PTM_RUN"]) / ".env").items():
        assert os.environ.get(key, None) == value, (
            f"{key}: {os.environ.get(key, None)}!={value}"
        )
