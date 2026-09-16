from __future__ import annotations

import sys
import types
from pathlib import Path


class Plain:
    def __init__(self, text: str) -> None:
        self.text = text


class MessageChain:
    def __init__(self, chain: list[object] | None = None) -> None:
        self.chain = chain or []


class FakeStar:
    def __init__(self, context) -> None:
        self.context = context


def install_astrbot_stubs(data_dir: Path | None = None) -> None:
    modules = {
        name: types.ModuleType(name)
        for name in (
            "astrbot",
            "astrbot.api",
            "astrbot.api.event",
            "astrbot.api.message_components",
            "astrbot.api.star",
            "astrbot.core",
            "astrbot.core.star",
            "astrbot.core.star.filter",
            "astrbot.core.star.filter.command",
        )
    }
    modules["astrbot.api"].AstrBotConfig = dict
    modules["astrbot.api"].logger = types.SimpleNamespace(
        warning=lambda *args, **kwargs: None,
        exception=lambda *args, **kwargs: None,
    )
    modules["astrbot.api.event"].AstrMessageEvent = object
    modules["astrbot.api.event"].filter = types.SimpleNamespace(
        command=lambda _name: lambda function: function,
    )
    modules["astrbot.api.message_components"].Plain = Plain
    modules["astrbot.api.event"].MessageChain = MessageChain
    modules["astrbot.api.star"].Context = object
    modules["astrbot.api.star"].Star = FakeStar
    modules["astrbot.api.star"].StarTools = types.SimpleNamespace(
        get_data_dir=lambda _name: data_dir or Path(".cache"),
    )
    modules["astrbot.api.star"].register = (
        lambda *_args, **_kwargs: lambda cls: cls
    )
    modules["astrbot.core.star.filter.command"].GreedyStr = str
    sys.modules.update(modules)


install_astrbot_stubs()
