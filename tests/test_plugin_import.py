from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_main_can_be_loaded_by_file_from_outside_plugin_directory(
    tmp_path: Path,
) -> None:
    main_path = Path(__file__).resolve().parents[1] / "main.py"
    loader_script = r"""
import importlib.util
import sys
import types

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
modules["astrbot.api"].logger = types.SimpleNamespace(
    warning=lambda *args, **kwargs: None,
)
modules["astrbot.api.event"].AstrMessageEvent = object
modules["astrbot.api.event"].MessageChain = type("MessageChain", (), {})
modules["astrbot.api.event"].filter = types.SimpleNamespace(
    command=lambda _name: lambda function: function,
)
modules["astrbot.api.message_components"].Plain = type("Plain", (), {})
modules["astrbot.api.star"].Context = object
modules["astrbot.api.star"].Star = object
modules["astrbot.api.star"].StarTools = object
modules["astrbot.api.star"].register = lambda *args, **kwargs: lambda cls: cls
modules["astrbot.core.star.filter.command"].GreedyStr = str
sys.modules.update(modules)

main_path = sys.argv[1]
spec = importlib.util.spec_from_file_location("astrbot_dynamic_plugin", main_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)
"""

    result = subprocess.run(
        [sys.executable, "-c", loader_script, str(main_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
