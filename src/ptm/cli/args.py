import typing as t

from click import Context, Parameter, ParamType
from click.globals import get_current_context
from click.shell_completion import CompletionItem
from typer import Argument, Option
from typing_extensions import Annotated

from ..config import Config, Environment, Run


class RunParser(ParamType):
    def convert(
        self, value: t.Any, param: t.Optional[Parameter], ctx: t.Optional[Context]
    ):
        if isinstance(value, Run):
            return value
        ctx = get_current_context()
        cfg: Config = ctx.obj["config"]
        return cfg.id_table[value.lower()]

    __name__: str = "RUN"


def complete_run(
    ctx: Context, param: Parameter, incomplete: str
) -> t.List[CompletionItem]:
    cfg: Config = ctx.obj["config"]
    items = []
    envs = [env.name for env in ctx.params.get("envs", [])]
    tags = ctx.params.get("tags", [])
    runs = (
        [run.ident for run in (ctx.params.get(param.name) or []) if run]
        if param.name
        else []
    ) or []
    for identifier, run in cfg.id_table.items():
        if (envs and run.group.env.name not in envs) or (
            tags and not any(tg in tags for tg in run.tags)
        ):
            continue
        if identifier.startswith(incomplete.lower()) and identifier not in runs:
            items.append(
                CompletionItem(
                    f"{incomplete}{identifier[len(incomplete) :]}", help=run.slug
                )
            )
    return items


class EnvParser(ParamType):
    def convert(
        self, value: t.Any, param: t.Optional[Parameter], ctx: t.Optional[Context]
    ):
        if isinstance(value, Run):
            return value
        ctx = get_current_context()
        cfg: Config = ctx.obj["config"]
        return cfg.environments[value.lower()]

    __name__: str = "ENV"


def complete_env(
    ctx: Context, param: Parameter, incomplete: str
) -> t.List[CompletionItem]:
    cfg: Config = ctx.obj["config"]
    items = []
    envs = (
        [env.name for env in ctx.params.get(param.name) or []] if param.name else []
    ) or []
    for env_name in cfg.environments.keys():
        if env_name.startswith(incomplete) and env_name not in envs:
            items.append(CompletionItem(env_name))

    return items


def complete_tag(
    ctx: Context, param: Parameter, incomplete: str
) -> t.List[CompletionItem]:
    cfg: Config = ctx.obj["config"]
    items = []
    tags = (ctx.params.get(param.name) if param.name else []) or []
    for tag in cfg.tag_table.keys():
        if tag.startswith(incomplete) and tag not in tags:
            items.append(CompletionItem(tag))
    return items


Environments = Annotated[
    t.List[Environment],
    Option(
        "--env",
        "-e",
        parser=EnvParser(),
        shell_complete=complete_env,
        help="Generate only the given environments.",
    ),
]

Tags = Annotated[
    t.List[str],
    Option(
        "--tags",
        "-t",
        shell_complete=complete_tag,
        help="Generate only the given tagged runs.",
    ),
]

Runs = Annotated[
    t.Optional[t.List[Run]],
    Argument(
        parser=RunParser(), shell_complete=complete_run, help="The run identifier."
    ),
]
