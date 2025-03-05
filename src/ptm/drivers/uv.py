import os
import subprocess
from contextlib import contextmanager
from itertools import chain

from ..config import Run
from . import GenerationFailed


class UVDriver:
    DEFAULT_ENVIRONMENT = os.environ.get("PTM_DEFAULT_ENV", "uv sync")

    def generate(self, run: Run):
        """Generate some output based on input data."""
        req_file = run.directory / "requirements.in"
        resolution = ["--resolution", run.strategy] if run.strategy else []
        extras = list(chain.from_iterable((("--extra", extra) for extra in run.extras)))
        groups = list(chain.from_iterable((("--group", group) for group in run.groups)))
        if "dev" not in groups:
            groups.append("--no-dev")
        try:
            cmd = ["uv", "export", "--no-hashes", *resolution, *extras, *groups]
            print(" ".join(cmd))
            with open(req_file, "w") as req_out:
                subprocess.run(cmd, check=True, stdout=req_out)
        except subprocess.CalledProcessError as err:
            print(run.directory)
            raise GenerationFailed(err.stderr) from err

        modified = []
        relieved = set()
        deps = {dep.package for dep in run.dependencies}
        for line in req_file.read_text().splitlines():
            if "==" in line and not line.strip().startswith("#"):
                pkg = line.split("==")[0]
                if pkg in deps:
                    if pkg not in relieved:
                        modified.append(pkg)
                    relieved.add(pkg)
                    continue
            modified.append(line)

        req_file.write_text(os.linesep.join(modified))

        constraints = run.directory / "constraints.in"
        constraints.write_text(os.linesep.join(str(dep) for dep in run.dependencies))

        try:
            cmd = [
                "uv",
                "pip",
                "compile",
                *resolution,
                "--python-version",
                run.python,
                # "--python-preference", "managed",
                "-c",
                str(constraints),
                str(req_file),
            ]
            print(" ".join(cmd).replace(f"{run.directory}/", ""))
            finalized = run.directory / "requirements.txt"
            with open(finalized, "w") as req_out:
                subprocess.run(cmd, check=True, stdout=req_out)
        except subprocess.CalledProcessError as err:
            print(run.directory)
            raise GenerationFailed(err.stderr) from err

    @contextmanager
    def bootstrap(self, run: Run, revert: bool = True):
        """
        Set up anything required before generating.
        """
        "uv pip install --exact"
        try:
            requirements = run.directory / "requirements.txt"
            if not requirements.is_file() or not requirements.stat().st_size:
                self.generate(run)
            yield subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    run.python,
                    "--exact",
                    "-r",
                    str(requirements),
                ],
                check=True,
            )
        finally:
            if revert and self.DEFAULT_ENVIRONMENT:
                subprocess.run(self.DEFAULT_ENVIRONMENT.split(), check=False)
