import hashlib
import itertools
import os
import shutil
import sys
import typing as t
import warnings
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cached_property
from pathlib import Path

import requests
import tomlkit
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import NormalizedName, canonicalize_name
from packaging.version import InvalidVersion, parse
from tomlkit.container import Container
from tomlkit.items import String, Table

from . import __version__ as ptm_version
from .drivers import GenerationFailed


class PTMDriver(t.Protocol):
    def generate(self, run: "Run") -> Path:
        """
        Generate a file that will allow this driver to bootstrap a virtual environment
        (e.g. requirements.txt) for this run later.
        """
        ...

    def bootstrap(self, run: "Run"):
        """
        Install the virtual environment for the given run.
        """
        ...


drivers: t.Dict[str, PTMDriver] = {}


def register_driver(tool: str, driver: PTMDriver):
    global drivers
    drivers[tool] = driver


def get_driver(tool: str) -> PTMDriver:
    return drivers[tool]


class DuplicateRunError(Exception):
    id: str

    def __init__(self, id: str):
        self.id = id


def hash_list(*strings: str) -> str:
    hasher = hashlib.sha256()
    for s in strings:
        hasher.update(s.encode("utf-8"))
    return hasher.hexdigest()


class ResolutionStrategy(StrEnum):
    HIGHEST = "highest"
    LOWEST = "lowest"
    LOWEST_DIRECT = "lowest-direct"


@dataclass
class Dependency:
    package: NormalizedName
    specifier: SpecifierSet

    def __str__(self) -> str:
        return f"{self.package}{self.specifier}"

    @staticmethod
    def parse(package: str, dep: str) -> "Dependency":
        package = canonicalize_name(package, validate=True)
        specifier: SpecifierSet
        try:
            specifier = SpecifierSet(dep)
        except InvalidSpecifier:
            # we must determine a default specifier operator
            # which will be == for all cases but major.minor, where
            # we choose ~= major.minor.0
            try:
                version = parse(dep)
                if (
                    version.is_devrelease
                    or version.is_postrelease
                    or version.is_prerelease
                ):
                    specifier = SpecifierSet(f"=={dep}")
                elif dep.count(".") == 1:
                    specifier = SpecifierSet(f"~={dep}.0")
                else:
                    specifier = SpecifierSet(f"=={dep}")
            except InvalidVersion:
                raise ValueError(f"Invalid dependency specifier: {package}={dep}")
        return Dependency(package=package, specifier=specifier)


@dataclass
class Run:
    python: str
    dependencies: t.List[Dependency]
    group: "RunGroup"

    @cached_property
    def name(self) -> str:
        return ",".join(str(dep) for dep in (self.python, *self.dependencies))

    def pformat(self) -> str:
        return f"{self.name}\n\t{self.setenv=}\n\t{self.groups=}\n\t{self.extras=}"

    @cached_property
    def id(self) -> str:
        return hash_list(
            f"version={ptm_version}",  # invalidate the runs if the version is upgraded
            f"strategy={self.strategy}",
            "python=",
            str(self.python),
            "deps=",
            *(str(dep) for dep in self.dependencies),
            "env=",
            *(f"{key}={val}" for key, val in self.setenv.items()),
            "groups=",
            *self.groups,
            "extras=",
            *self.extras,
        )

    def __post_init__(self):
        if self.id in self.group.env.cfg.id_table:
            raise DuplicateRunError(self.id)
        for tag in self.tags:
            self.group.env.cfg.tag_table.setdefault(tag, [])
            self.group.env.cfg.tag_table[tag].append(self)

    @property
    def directory(self) -> Path:
        return self.group.env.directory / self.id

    @property
    def strategy(self) -> t.Optional[ResolutionStrategy]:
        return (
            self.group.strategy
            or self.group.env.strategy
            or self.group.env.cfg.strategy
        )

    @property
    def setenv(self) -> t.Dict[str, str]:
        return {
            **self.group.env.cfg.setenv,
            **self.group.env.setenv,
            **self.group.setenv,
        }

    @property
    def tags(self) -> t.List[str]:
        return list(set((*self.group.env.tags, *self.group.tags)))

    @property
    def groups(self) -> t.List[str]:
        return list(
            set(
                (*self.group.env.cfg.groups, *self.group.env.groups, *self.group.groups)
            )
        )

    @property
    def extras(self) -> t.List[str]:
        return list(
            set(
                (*self.group.env.cfg.extras, *self.group.env.extras, *self.group.extras)
            )
        )

    @property
    def env_file(self) -> Path:
        return self.directory / ".env"

    def generate(self) -> "Run":
        os.makedirs(self.directory, exist_ok=True)
        self.env_file.write_text(
            "\n".join(f'{key}="{val}"' for key, val in self.setenv.items())
        )
        try:
            self.group.env.cfg.driver.generate(self)
        except GenerationFailed as gf:
            print(gf)
            sys.exit(1)
        return self


@dataclass
class RunGroup:
    env: "Environment"
    matrix: t.Dict[str, t.List[str]]
    strategy: t.Optional[ResolutionStrategy] = None
    setenv: t.Dict[str, str] = field(default_factory=dict)
    tags: t.List[str] = field(default_factory=list)
    groups: t.List[str] = field(default_factory=list)
    extras: t.List[str] = field(default_factory=list)
    lineno: t.Optional[int] = None

    runs: t.List[Run] = field(default_factory=list)

    def __post_init__(self):
        self.expand()

    def expand(self) -> t.List[Run]:
        assert "python" in self.matrix, (
            "`ptm.env.matrix` entries must include `python`."
        )
        expanded = [
            dict(zip(list(self.matrix.keys()), spec))
            for spec in itertools.product(
                *(
                    [spec] if isinstance(spec, str) else spec
                    for spec in self.matrix.values()
                )
            )
        ]
        for idx, run in enumerate(expanded):
            try:
                self.runs.append(
                    Run(
                        python=self.env.cfg.resolve_alias(run["python"]),
                        dependencies=[
                            Dependency.parse(pkg, self.env.cfg.resolve_alias(spec))
                            for pkg, spec in run.items()
                            if pkg != "python"
                        ],
                        group=self,
                    )
                )
            except DuplicateRunError:
                warnings.warn(f"Expanded run {idx} of ")
        return self.runs

    @staticmethod
    def from_toml(env: "Environment", run_group: Table) -> "RunGroup":
        return RunGroup(
            env=env,
            matrix={
                dep: spec for dep, spec in run_group.items() if not dep.startswith("-")
            },
            **{
                param.lstrip("-"): value
                for param, value in run_group.items()
                if param.startswith("-")
            },
        )

    def generate(self, tags: t.Set[str] = {}) -> t.Generator[Run, None, None]:
        for run in self.runs:
            if not tags or any((tag in tags for tag in run.tags)):
                yield run.generate()


@dataclass
class Environment:
    name: str
    cfg: "Config"
    strategy: t.Optional[ResolutionStrategy] = None
    setenv: t.Dict[str, str] = field(default_factory=dict)
    tags: t.List[str] = field(default_factory=list)
    groups: t.List[str] = field(default_factory=list)
    extras: t.List[str] = field(default_factory=list)
    matrix: t.List[RunGroup] = field(default_factory=list)

    @property
    def directory(self) -> Path:
        return self.cfg.directory / self.name

    def generate(self, tags: t.Set[str] = {}) -> t.Generator[Run, None, None]:
        if self.directory.exists():
            shutil.rmtree(self.directory)
        os.makedirs(self.directory, exist_ok=True)
        for grp in self.matrix:
            yield from grp.generate(tags=tags)

    @staticmethod
    def from_toml(
        name: str, cfg: "Config", env: t.Union[Container, Table, String]
    ) -> "Environment":
        if isinstance(env, String):
            resp = requests.get(env)
            resp.raise_for_status()
            env = tomlkit.parse(resp.text)
        parsed_env = Environment(
            name=name,
            cfg=cfg,
            **{
                param: env[param]
                for param in ["strategy", "setenv", "tags", "groups", "extras"]
                if param in env
            },
        )
        parsed_env.matrix = [
            RunGroup.from_toml(parsed_env, run) for run in env.get("matrix", [])
        ]
        return parsed_env


@dataclass
class Config:
    project_dir: Path
    driver: PTMDriver = field(default_factory=lambda: get_driver("uv")())
    strategy: t.Optional[ResolutionStrategy] = None
    setenv: t.Dict[str, str] = field(default_factory=dict)
    dot_dir: str = ".ptm"
    groups: t.List[str] = field(default_factory=lambda: ["dev"])
    extras: t.List[str] = field(default_factory=list)
    aliases: t.Dict[str, str] = field(default_factory=dict)
    environments: t.Dict[str, Environment] = field(default_factory=dict)

    # maps tags to runs
    tag_table: t.Dict[str, Run] = field(default_factory=dict)

    id_table: t.Dict[str, Run] = field(default_factory=dict)

    def resolve_alias(self, name: str) -> str:
        return self.aliases.get(name, name)

    @property
    def directory(self) -> Path:
        return self.project_dir / self.dot_dir

    @staticmethod
    def from_toml(config_path: Path, doc: tomlkit.TOMLDocument) -> "Config":
        section = doc["tool"]["ptm"]
        assert isinstance(section, Table), "`tool.ptm` must be configured."
        driver = {}
        if "driver" in section:
            driver["driver"] = get_driver(section["driver"])()
        cfg = Config(
            project_dir=config_path.parent,
            **{
                param: section[param]
                for param in [
                    "strategy",
                    "setenv",
                    "dot_dir",
                    "extras",
                    "groups",
                    "aliases",
                ]
                if param in section
            },
            **driver,
        )

        assert "env" in section and isinstance(section["env"], dict), (
            "`tool.ptm.env` must be configured correctly."
        )
        for env_name, env in t.cast(Table, section["env"]).items():
            cfg.environments[env_name] = Environment.from_toml(env_name, cfg, env)
        return cfg

    def generate(
        self, environments: t.Set[str] = {}, tags: t.Set[str] = {}
    ) -> t.Generator[Run, None, None]:
        for name, env in self.environments.items():
            if not environments or name in environments:
                yield from env.generate(tags=tags)


def initialize(cfg_file: t.Optional[Path] = None) -> Config:
    from .drivers.uv import UVDriver

    register_driver("uv", UVDriver)
    config = cfg_file or find_config()
    if config is None or not config.exists():
        raise ValueError("No configuration file found.")
    cfg = Config.from_toml(config, tomlkit.parse(config.read_text()))
    os.makedirs(cfg.directory, exist_ok=True)
    return cfg


def find_config() -> t.Optional[Path]:
    # starting from cwd, traverse upwards until we find a pyproject.toml file
    # if we don't find one, return None
    current_dir = Path.cwd()
    while current_dir != Path("/"):
        pyproj = current_dir / "pyproject.toml"
        if pyproj.exists():
            return pyproj
        current_dir = current_dir.parent
    return None
