"""endfield-theme 单元测试：变体解析 / preamble 生成 / 注入-移除闭环。

反向验证设计：关键断言直接对照官方 HTML 原文与变体表数值，
改回旧实现（如不压 !important、不清理字体）会让用例失败。
"""

from __future__ import annotations

import asyncio
import pathlib
import sys
import tempfile
import types

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
PLUGIN_DIR = TESTS_DIR.parent
sys.path.insert(0, str(TESTS_DIR))

from fakehost import FakeHost, bind_context, build_context, get_default_config, load_plugin_module  # noqa: E402

OFFICIAL_HTML = (
    "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
    "<title>MaiBot Dashboard</title></head><body><div id=\"root\"></div></body></html>"
)


@pytest.fixture()
def module():
    return load_plugin_module(PLUGIN_DIR)


@pytest.fixture()
def env(module):
    """插件实例 + 临时 dist + 假 maibot_dashboard。"""
    plugin = module.create_plugin()
    host = FakeHost(plugin_id="github.orge-8.endfield-theme")
    ctx = build_context("github.orge-8.endfield-theme", rpc_call=host.rpc_call)
    bind_context(plugin, ctx, get_default_config(type(plugin).config_model))
    with tempfile.TemporaryDirectory() as tmp:
        dist = pathlib.Path(tmp) / "dist"
        dist.mkdir()
        (dist / "index.html").write_text(OFFICIAL_HTML, encoding="utf-8")
        mod = types.ModuleType("maibot_dashboard")
        mod.get_dist_path = lambda: str(dist)
        old = sys.modules.get("maibot_dashboard")
        sys.modules["maibot_dashboard"] = mod
        yield plugin, dist
        if old is not None:
            sys.modules["maibot_dashboard"] = old
        else:
            sys.modules.pop("maibot_dashboard", None)


def _apply(plugin):
    asyncio.run(plugin.on_load())


def _set_config(plugin, **appearance):
    cfg = get_default_config(type(plugin).config_model)
    cfg["appearance"].update(appearance)
    bind_context(plugin, plugin.ctx, cfg)
    return cfg


# ---------------------------------------------------------------- 变体解析

def test_resolve_defaults(module):
    v = module.resolve("lime", "neutral", "compact")
    assert v["accentHex"] == "#B8FF3D"
    assert v["scale"] == 0.9375
    assert v["light"]["paper"] == "#F4F4F2"
    assert v["dark"]["paper"] == "#191919"


def test_resolve_invalid_falls_back(module):
    v = module.resolve("red", "hot", "huge")
    assert v["accent"] == "lime"
    assert v["paper"] == "neutral"
    assert v["density"] == "compact"


def test_resolve_all_combinations(module):
    for a in ("yellow", "lime", "ice", "amber"):
        for p in ("neutral", "warm", "cool"):
            for d in ("compact", "standard", "roomy"):
                v = module.resolve(a, p, d)
                assert v["accent"] == a and v["paper"] == p and v["density"] == d


def test_hex_to_hsl_known_values(module):
    from importlib import import_module
    ev = import_module("endfield_theme.et_variants")
    assert ev.hex_to_hsl("#FFFFFF") == "0.0 0.0% 100.0%"
    assert ev.hex_to_hsl("#000000") == "0.0 0.0% 0.0%"
    assert ev.hex_to_hsl("#FF0000") == "0.0 100.0% 50.0%"


# ---------------------------------------------------------------- preamble

def test_preamble_important_overrides(module):
    v = module.resolve("yellow", "neutral", "standard")
    pre = module.build_preamble(v)
    # dashboard 管线写行内样式，必须 !important 才压得住
    assert "--color-primary:59.6 100% 50% !important" in pre
    assert "--visual-radius-lg:0px !important" in pre
    assert "--visual-shadow-md:none !important" in pre
    assert "html.dark{" in pre, "缺深色主题块"


def test_preamble_dark_trace_is_accent(module):
    v = module.resolve("ice", "cool", "standard")
    pre = module.build_preamble(v)
    dark_block = pre.split("html.dark{")[1]
    # 深色主题 ring/trace = 强调色；浅色 = 墨色
    assert "--color-ring:191.9 100% 74.5% !important" in dark_block
    light_block = pre.split("html.dark{")[0]
    assert "--color-ring:0.0 0.0% 8.6% !important" in light_block


def test_preamble_density_scales_type(module):
    compact = module.build_preamble(module.resolve("lime", "neutral", "compact"))
    roomy = module.build_preamble(module.resolve("lime", "neutral", "roomy"))
    assert "--typography-font-size-base:0.9375rem !important" in compact
    assert "--typography-font-size-base:1.0625rem !important" in roomy


def test_preamble_paper_variants_differ(module):
    warm = module.build_preamble(module.resolve("lime", "warm", "standard"))
    cool = module.build_preamble(module.resolve("lime", "cool", "standard"))
    assert "--ef-paper:#F3F1EA" in warm
    assert "--ef-paper:#F0F3F5" in cool
    assert warm != cool


# ---------------------------------------------------------------- 注入闭环

def test_inject_and_idempotent(env):
    plugin, dist = env
    _apply(plugin)
    index = dist / "index.html"
    html = index.read_text(encoding="utf-8")
    assert 'id="endfield-theme-style"' in html
    assert html.count('id="endfield-theme-style"') == 1
    _apply(plugin)
    assert index.read_text(encoding="utf-8") == html, "重复 apply 必须幂等"


def test_fonts_installed(env):
    plugin, dist = env
    _apply(plugin)
    fdir = dist / "fonts" / "endfield"
    assert (fdir / "Saira.ttf").is_file()
    assert (fdir / "Saira-OFL.txt").is_file(), "OFL 许可证必须随字体分发"
    assert (fdir / "fonts.css").is_file()
    assert (fdir / "Saira.ttf").stat().st_size == (PLUGIN_DIR / "fonts" / "Saira.ttf").stat().st_size


def test_contours_installed_and_removed(env):
    """等高线 SVG 随注入分发、随停用/卸载清理（CSS mask 引用 dist 内路径）。"""
    plugin, dist = env
    _apply(plugin)
    fdir = dist / "fonts" / "endfield"
    for name in ("contour-a.svg", "contour-b.svg"):
        assert (fdir / name).is_file(), f"{name} 未随注入分发"
        assert (fdir / name).stat().st_size == (PLUGIN_DIR / "theme" / "contours" / name).stat().st_size
    asyncio.run(plugin.on_unload())
    assert not (dist / "fonts" / "endfield").exists(), "卸载后等高线未清理"


def test_css_contours_and_motion():
    """等高线可见性 + 动效语法：删掉任一关键实现都会失败。"""
    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    # 等高线：两角 mask、引用 dist 内 SVG、铺在主区
    assert "contour-a.svg" in css and "contour-b.svg" in css
    assert "[data-observation-shell='true']::before" in css
    assert "var(--ef-contour)" in css
    # 动效：通电/擦入/快门关键帧 + 对话框/浮层/提示条/标签页接入
    for kf in ("ef-power-on", "ef-power-off", "ef-wipe-in", "ef-wipe-out", "ef-shutter-in", "ef-come"):
        assert f"@keyframes {kf}" in css, f"缺关键帧 {kf}"
    assert "[role='dialog'][data-state='open']" in css
    assert "[data-sonner-toast][data-state='open']" in css
    assert "[role='tabpanel'][data-state='active']" in css
    # 记录行：右移 6px + 左色条
    assert "translateX(6px)" in css
    # 减少动态效果保护仍在
    assert "prefers-reduced-motion: reduce" in css
    assert "prefers-reduced-motion: no-preference" in css
    # preamble 提供 18% 等高线变量（高于 skill 基准 9%，用户要求加强）
    from importlib import import_module
    ev = import_module("endfield_theme.et_variants")
    pre = ev.build_preamble(ev.resolve("lime", "neutral", "compact"))
    assert "--ef-contour:color-mix(in srgb, var(--ef-ink) 18%, transparent)" in pre


def test_config_update_switches_accent(env):
    plugin, dist = env
    _apply(plugin)
    _set_config(plugin, accent="amber")
    asyncio.run(plugin.on_config_update("self", {}, "0.2.0"))
    html = (dist / "index.html").read_text(encoding="utf-8")
    assert "--ef-accent:#FFB31F" in html
    assert "--ef-accent:#B8FF3D" not in html, "旧强调色残留"
    assert html.count('id="endfield-theme-style"') == 1


def test_disable_restores_official(env):
    plugin, dist = env
    _apply(plugin)
    cfg = get_default_config(type(plugin).config_model)
    cfg["plugin"]["enabled"] = False
    bind_context(plugin, plugin.ctx, cfg)
    asyncio.run(plugin.on_config_update("self", cfg, "0.2.0"))
    assert (dist / "index.html").read_text(encoding="utf-8") == OFFICIAL_HTML
    assert not (dist / "fonts" / "endfield").exists()


def test_unload_restores_official(env):
    plugin, dist = env
    _apply(plugin)
    asyncio.run(plugin.on_unload())
    assert (dist / "index.html").read_text(encoding="utf-8") == OFFICIAL_HTML
    assert not (dist / "fonts" / "endfield").exists()


def test_unload_without_inject_is_noop(env):
    plugin, dist = env
    asyncio.run(plugin.on_unload())
    assert (dist / "index.html").read_text(encoding="utf-8") == OFFICIAL_HTML


def test_missing_head_skips_inject(env):
    plugin, dist = env
    (dist / "index.html").write_text("<html><body>no head</body></html>", encoding="utf-8")
    _apply(plugin)
    assert 'id="endfield-theme-style"' not in (dist / "index.html").read_text(encoding="utf-8")


def test_foreign_style_untouched(env):
    plugin, dist = env
    foreign = '<style id="other-plugin">body{color:red}</style>'
    html = OFFICIAL_HTML.replace("</head>", foreign + "</head>")
    (dist / "index.html").write_text(html, encoding="utf-8")
    _apply(plugin)
    injected = (dist / "index.html").read_text(encoding="utf-8")
    assert foreign in injected, "不得动其他插件的注入块"
    asyncio.run(plugin.on_unload())
    assert (dist / "index.html").read_text(encoding="utf-8") == html, "卸载只清自己的块"


# ---------------------------------------------------------------- 配置页中文化

def test_config_schema_localized(module):
    """配置页中文显示：字段 label / 选项 choice:i18n / hint 必须齐全。

    反向验证：dashboard plugin-config.tsx 的 select 渲染只认
    i18n["<locale>"]["choice:<值>"]，未声明时回退英文枚举值；
    字段标签未声明 label 时回退英文字段名；字段说明只渲染 hint。
    删掉任一声明都会让本用例失败。
    """
    from maibot_sdk.config import generate_plugin_config_schema

    schema = generate_plugin_config_schema(module.EndfieldThemeConfig)
    appearance = schema["sections"]["appearance"]
    assert appearance["title"] == "外观"
    assert appearance["i18n"]["zh-CN"]["title"] == "外观"

    expected_labels = {"accent": "强调色", "paper": "纸色", "density": "密度"}
    expected_choices = {
        "accent": {
            "yellow": "标准黄（#FFFA00）", "lime": "青柠（#B8FF3D）",
            "ice": "冰蓝（#7DE6FF）", "amber": "琥珀（#FFB31F）",
        },
        "paper": {"neutral": "中性灰白", "warm": "暖米色", "cool": "冷青灰"},
        "density": {
            "compact": "紧凑（0.9375）", "standard": "标准（1）", "roomy": "宽松（1.0625）",
        },
    }
    for name, label in expected_labels.items():
        field = appearance["fields"][name]
        assert field["label"] == label, f"{name} 标签未中文化"
        zh = field["i18n"]["zh-CN"]
        assert zh["label"] == label
        assert zh.get("hint"), f"{name} 缺 hint（前端不渲染 description）"
        for choice in field["choices"]:
            assert zh[f"choice:{choice}"] == expected_choices[name][choice], \
                f"{name} 选项 {choice} 显示名缺失或不符"
            assert field["i18n"]["en-US"][f"choice:{choice}"], f"{name}/{choice} 缺英文对照"

    plugin_section = schema["sections"]["plugin"]
    enabled = plugin_section["fields"]["enabled"]
    assert enabled["label"] == "启用主题"
    assert enabled["i18n"]["zh-CN"]["label"] == "启用主题"


def test_css_assets_exist_and_nonempty():
    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    assert "clip-path" in css, "切角语法缺失"
    assert "prefers-reduced-motion" in css, "缺减少动态效果保护"
    assert "--ef-accent" in css
    fonts = (PLUGIN_DIR / "theme" / "fonts.css").read_text(encoding="utf-8")
    assert "font-stretch: 50% 125%" in fonts, "Saira 可变宽度轴声明缺失"
