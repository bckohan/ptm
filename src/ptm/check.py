import os
import sys
from importlib.metadata import version as pkg_version

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
        assert pkg_version(req.name) in req.specifier, (
            f"Unexpected package version {req} != {pkg_version(req.name)}"
        )

    # todo check environment
