import os
import subprocess
from itertools import chain
from pathlib import Path

from ..config import Run
from . import GenerationFailed


class UVDriver:
    def generate(self, run: Run) -> Path:
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

    def bootstrap(self) -> None:
        """Set up anything required before generating."""
        "uv pip install --exact"
