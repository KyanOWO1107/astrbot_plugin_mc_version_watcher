from __future__ import annotations

from collections.abc import Mapping, Sequence

from .models import MANIFEST_URL, VersionInfo, classify_version


def _label_suffix(version: VersionInfo) -> str:
    label = classify_version(version)
    return label.split("（", 1)[1].rstrip("）") if "（" in label else label


def format_latest(latest: Mapping[str, VersionInfo | None]) -> str:
    lines = ["Minecraft 最新版本"]
    if not latest:
        return "Minecraft 最新版本\n\n未启用任何版本类型。"
    for version_type, version in latest.items():
        if version is None:
            lines.append(f"{version_type.capitalize()}：当前没有匹配版本")
        else:
            lines.append(
                f"{version_type.capitalize()}：{version.id}（{_label_suffix(version)}）"
            )
    return "\n".join(lines)


def format_update_message(
    versions: Sequence[VersionInfo],
    *,
    test: bool = False,
) -> str:
    title = "Minecraft 版本更新（测试模拟）" if test else "Minecraft 版本更新"
    lines = [title, ""]
    for version in versions:
        lines.extend([f"- 版本：{version.id}", f"  分类：{classify_version(version)}"])
        if version.release_time:
            lines.append(f"  发布时间：{version.release_time}")
        lines.append("")
    lines.extend(["来源：Mojang 官方版本清单", MANIFEST_URL])
    return "\n".join(lines)


def format_test_update() -> str:
    return format_update_message(
        [VersionInfo("mc-version-watcher-test", "snapshot")],
        test=True,
    )


def format_delivery_summary(
    success_count: int,
    failures: Sequence[tuple[str, str]],
) -> str:
    lines = [f"模拟推送完成：成功 {success_count}，失败 {len(failures)}。"]
    for target, error in failures:
        lines.append(f"- {target}：{error}")
    return "\n".join(lines)


def format_usage() -> str:
    return (
        "用法：\n"
        "/mcversion latest：分别查询已启用类型的最新版本\n"
        "/mcversion umo：获取当前会话 UMO\n"
        "/mcversion test：管理员向已配置 UMO 发送模拟更新"
    )
