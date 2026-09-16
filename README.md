# Minecraft Version Watcher

用于 AstrBot 定时监测 Mojang 官方 Minecraft 版本清单并推送更新。

## 功能

- 默认每 5 分钟检查 `release` 和 `snapshot`。
- Release Candidate 和 Pre-release 按官方规范归入 `snapshot`，并在消息中标注。
- 支持配置私聊和群聊 UMO 推送目标。
- 首次成功检查只建立基线，不推送已有历史版本。
- 支持 `/mcversion latest`、`/mcversion umo`、管理员 `/mcversion test`。

## 配置

在 AstrBot 插件设置中配置检查间隔、监测类型和推送 UMO 列表：

- 检查间隔：分钟数，默认 5，最小按 1 处理。
- 监测类型：`release`、`snapshot`，默认两者都启用。
- 推送 UMO：每项填写一个完整 UMO。

先在目标私聊或群聊中发送 `/mcversion umo`，再把返回值复制到推送 UMO 列表。

## 命令

- `/mcversion latest`：分别获取已启用类型的最新版本。
- `/mcversion umo`：获取当前会话 UMO。
- `/mcversion test`：管理员向全部配置目标发送真实模拟推送，不访问 Mojang，也不修改版本状态。

## 数据和故障处理

版本来源为 Mojang 官方 manifest：

`https://piston-meta.mojang.com/mc/game/version_manifest_v2.json`

状态文件位于 AstrBot 的：

`data/plugin_data/astrbot_plugin_mc_version_watcher/state.json`

网络失败会保留旧状态并在下一周期重试。单个 UMO 发送失败不会阻塞其他目标；失败会记录到日志。

## 安装

将本目录作为插件目录放入 AstrBot 的插件目录，并按 AstrBot 的插件管理流程加载或重载。插件只使用 Python 标准库和 AstrBot API，不需要额外运行时依赖。

## 开发检查

```powershell
python -m pytest -q
python -m compileall -q .
```

离线单元测试不依赖实时 Mojang 接口，也不能替代真实 AstrBot 适配器验收。安装到 AstrBot 后，应使用 `/mcversion umo` 和管理员 `/mcversion test` 验证实际主动推送链路。
