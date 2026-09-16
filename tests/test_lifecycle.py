from __future__ import annotations

import asyncio

from main import MinecraftVersionWatcherPlugin, PluginSettings


def test_initialize_creates_one_task_and_terminate_cancels_it() -> None:
    async def scenario() -> None:
        plugin = MinecraftVersionWatcherPlugin.__new__(MinecraftVersionWatcherPlugin)
        plugin.settings = PluginSettings(1, (), ())
        plugin._poll_task = None

        async def poll_loop():
            await asyncio.Event().wait()

        plugin._poll_loop = poll_loop
        await plugin.initialize()
        task = plugin._poll_task
        assert task is not None
        await plugin.initialize()
        assert plugin._poll_task is task
        await plugin.terminate()
        assert task.cancelled()
        assert plugin._poll_task is None

    asyncio.run(scenario())
