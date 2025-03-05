import typing as t

from click import Context, Parameter, ParamType
from click.globals import get_current_context
from click.shell_completion import CompletionItem

from ..config import Config, Run


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
    # todo restrict to environments if present
    items = []
    for identifier, run in cfg.id_table.items():
        if identifier.startswith(incomplete.lower()):
            items.append(
                CompletionItem(
                    f"{incomplete}{identifier[len(incomplete) :]}", help=run.slug
                )
            )
    return items
