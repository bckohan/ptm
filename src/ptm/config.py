import os
import shutil
import typing as t
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import requests
import tomlkit
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import NormalizedName, canonicalize_name
from packaging.version import InvalidVersion, parse
from tomlkit.container import Container
from tomlkit.items import Array, Item, String, Table

"""
  {python = ["3.8"],  django = ["3.2"], groups=["psycopg2"], strategy="lowest", env={postgres="9.6"}},
"""


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
    env: "Environment"
    python: Dependency
    strategy: t.Optional[ResolutionStrategy] = None
    setenv: t.Dict[str, str] = field(default_factory=dict)
    tags: t.List[str] = field(default_factory=list)
    groups: t.List[str] = field(default_factory=list)
    extras: t.List[str] = field(default_factory=list)

    # @property
    # def strategy(self) -> t.Optional[ResolutionStrategy]:
    #     return self.strategy or self.env.strategy


@dataclass
class RunGroup:
    env: "Environment"
    strategy: t.Optional[ResolutionStrategy] = None
    setenv: t.Dict[str, str] = field(default_factory=dict)
    tags: t.List[str] = field(default_factory=list)
    groups: t.List[str] = field(default_factory=list)
    extras: t.List[str] = field(default_factory=list)
    matrix: t.List[t.Dict[str, t.List[str]]] = field(default_factory=list)

    runs: t.List[Run] = field(default_factory=list)

    def __post_init__(self):
        self.expand()

    def expand(self) -> t.List[Run]:
        # TODO
        return []


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

    def __post_init__(self):
        pass

    def generate(self) -> Path:
        if self.directory.exists():
            shutil.rmtree(self.directory)
        os.makedirs(self.directory, exist_ok=True)
        # groups = self.cfg.groups + self.groups
        return self.directory


@dataclass
class Config:
    project_dir: Path
    setenv: t.Dict[str, str] = field(default_factory=dict)
    dot_dir: str = ".ptm"
    groups: t.List[str] = field(default_factory=lambda: ["dev"])
    extras: t.List[str] = field(default_factory=list)
    aliases: t.Dict[str, str] = field(default_factory=dict)
    environments: t.Dict[str, Environment] = field(default_factory=dict)

    @property
    def directory(self) -> Path:
        return self.project_dir / self.dot_dir


def initialize(cfg_file: t.Optional[Path] = None) -> Config:
    config = cfg_file or find_config()
    if config is None or not config.exists():
        raise ValueError("No configuration file found.")
    cfg = read_config(config)
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


def _parse_run_group(env: Environment, run: Table) -> RunGroup:
    return RunGroup(
        env=env,
        setenv=run.get("setenv", {}),
        tags=run.get("tags", []),
        groups=run.get("groups", []),
        extras=run.get("extras", []),
    )


def _parse_env(
    name: str, cfg: Config, env: t.Union[Container, Table, String]
) -> Environment:
    if isinstance(env, String):
        resp = requests.get(_convert_to_native(env))
        resp.raise_for_status()
        env = tomlkit.parse(resp.text)
    config_params = {
        key
        for key in Environment.__dataclass_fields__.keys()
        if key not in ["name", "matrix"]
    }
    parsed_env = Environment(
        name=name,
        cfg=cfg,
        **{key: _convert_to_native(env[key]) for key in config_params if key in env},
    )
    parsed_env.matrix = [
        _parse_run_group(parsed_env, run) for run in env.get("matrix", [])
    ]
    return parsed_env


def read_config(config: Path) -> Config:
    # read the pyproject.toml file and return a Config object
    # tool.uv.test_matrix
    doc = tomlkit.parse(config.read_text())
    section = read_section(doc, "tool.uv.test_matrix")
    assert isinstance(section, Table), "`tool.uv.test.matrix` must be configured."
    config_params = {
        key for key in Config.__dataclass_fields__.keys() if key not in ["environments"]
    }
    cfg = Config(
        project_dir=config.parent,
        **{
            key: _convert_to_native(section[key])
            for key in config_params
            if key in section
        },
    )
    assert "env" in section and isinstance(section["env"], dict), (
        "`tool.uv.test_matrix.env` must be configured correctly."
    )
    for env_name, env in t.cast(Table, section["env"]).items():
        cfg.environments[env_name] = _parse_env(env_name, cfg, env)
    return cfg


def _convert_to_native(item: t.Union[Container, Table, Array, Item]) -> t.Any:
    """Convert tomlkit objects to native Python types recursively."""
    if isinstance(item, Table):
        return {k: _convert_to_native(v) for k, v in item.items()}
    elif isinstance(item, Array):
        return [_convert_to_native(v) for v in item]
    else:
        return item.unwrap()


def _is_container(obj: t.Any) -> bool:
    return hasattr(obj, "__contains__") and hasattr(obj, "__getitem__")


def read_section(
    doc: t.Union[tomlkit.TOMLDocument, Table, Container], section: str
) -> t.Optional[t.Union[Table, Item, Container]]:
    parts = section.split(".")
    current = doc
    for part in parts:
        if _is_container(current) and part in current:  # type: ignore
            current = current[part]  # type: ignore
        else:
            return None
    return current
