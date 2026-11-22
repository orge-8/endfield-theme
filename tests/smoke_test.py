"""冒烟测试：不启动 MaiBot，用 FakeHost + 假 dashboard dist 跑完插件生命周期。

运行: python tests/smoke_test.py
覆盖：注入 → 幂等 → 配置热更新重注入 → 停用移除 → 卸载还原。
"""

from __future__ import annotations

import asyncio
import pathlib
import sys
import tempfile
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent

OFFICIAL_HTML = (
    "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
    "<title>MaiBot Dashboard</title></head><body><div id=\"root\"></div></body></html>"
)


def _install_fake_dashboard(dist: pathlib.Path) -> None:
    """伪造 maibot_dashboard 模块，让插件把注入写进临时 dist。"""
    mod = types.ModuleType("maibot_dashboard")
    mod.get_dist_path = lambda: str(dist)
    sys.modules["maibot_dashboard"] = mod


def main() -> int:
    try:
        import maibot_sdk  # noqa: F401
    except Exception:
        print("SKIP: 未安装 maibot-plugin-sdk，跳过冒烟测试（这不代表通过）")
        return 0

    from fakehost import FakeHost, bind_context, build_context, get_default_config, load_plugin_module

    module = load_plugin_module(PLUGIN_DIR)
    plugin = module.create_plugin()
    host = FakeHost(plugin_id="github.orge-8.endfield-theme")
    ctx = build_context("github.orge-8.endfield-theme", rpc_call=host.rpc_call)
    bind_context(plugin, ctx, get_default_config(getattr(type(plugin), "config_model", None)))

    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dist = pathlib.Path(tmp) / "dist"
            dist.mkdir()
            index = dist / "index.html"
            index.write_text(OFFICIAL_HTML, encoding="utf-8")
            _install_fake_dashboard(dist)

            # 1. 加载即注入
            await plugin.on_load()
            html = index.read_text(encoding="utf-8")
            assert 'id="endfield-theme-style"' in html, "on_load 未注入样式块"
            assert 'id="endfield-theme-fonts"' in html, "on_load 未注入字体链接"
            assert "--ef-accent:#B8FF3D" in html, "默认 accent 应为 lime"
            assert (dist / "fonts" / "endfield" / "Saira.ttf").is_file(), "字体未拷入 dist"
            assert (dist / "fonts" / "endfield" / "fonts.css").is_file(), "fonts.css 未拷入 dist"

            # 2. 幂等：重复 apply 不产生重复块
            await plugin.on_load()
            html2 = index.read_text(encoding="utf-8")
            assert html2.count('id="endfield-theme-style"') == 1, "重复注入产生多个样式块"
            assert html2 == html, "幂等 apply 不应改写内容"

            # 3. 配置热更新：换 accent 后重注入
            cfg = get_default_config(type(plugin).config_model)
            cfg["appearance"]["accent"] = "ice"
            bind_context(plugin, ctx, cfg)
            await plugin.on_config_update("self", cfg, "0.2.1")
            html3 = index.read_text(encoding="utf-8")
            assert "--ef-accent:#7DE6FF" in html3, "热更新后 accent 未切换为 ice"
            assert html3.count('id="endfield-theme-style"') == 1, "热更新后样式块重复"

            # 4. 停用：移除注入与字体
            cfg["plugin"]["enabled"] = False
            bind_context(plugin, ctx, cfg)
            await plugin.on_config_update("self", cfg, "0.2.1")
            html4 = index.read_text(encoding="utf-8")
            assert html4 == OFFICIAL_HTML, "停用后未还原官方 index.html"
            assert not (dist / "fonts" / "endfield").exists(), "停用后字体目录未清理"

            # 5. 重新启用 + 卸载还原
            cfg["plugin"]["enabled"] = True
            bind_context(plugin, ctx, cfg)
            await plugin.on_config_update("self", cfg, "0.2.1")
            assert 'id="endfield-theme-style"' in index.read_text(encoding="utf-8")
            await plugin.on_unload()
            assert index.read_text(encoding="utf-8") == OFFICIAL_HTML, "卸载后未还原官方 index.html"

    asyncio.run(run())
    print("smoke: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
