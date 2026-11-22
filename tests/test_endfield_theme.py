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


def test_preamble_light_primary_is_ink(module):
    """浅色 primary=墨（text-primary 文字可读），深色 primary=强调色。

    反向验证：真机浅色模式曾把「运行中 1 / 当前 Bot 名 / GATEWAY 路径」
    渲染成强调色文字（白底对比度约 1.1:1）。改回 primary=accent 即失败。
    """
    v = module.resolve("lime", "neutral", "compact")
    pre = module.build_preamble(v)
    light_block = pre.split("html.dark{")[0]
    dark_block = pre.split("html.dark{")[1]
    ink_hsl = "0.0 0.0% 8.6%"
    accent_hsl = v["accentHsl"]
    assert f"--color-primary:{ink_hsl} !important" in light_block, "浅色 primary 必须是墨色"
    assert f"--color-primary:{accent_hsl} !important" not in light_block
    assert f"--color-primary:{accent_hsl} !important" in dark_block, "深色 primary 应为强调色"
    # 四种强调色下浅色 primary 恒为墨
    for a in ("yellow", "lime", "ice", "amber"):
        p = module.build_preamble(module.resolve(a, "neutral", "compact"))
        assert f"--color-primary:{ink_hsl} !important" in p.split("html.dark{")[0]


def test_css_accent_fills_and_status(module):
    """强调色只做填充：选中件显式 --ef-accent；状态色不用红绿。"""
    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    # 选中/当前填充件
    assert ".bg-primary.text-primary-foreground" in css
    # 分段条状态映射：emerald→accent、amber→斜线纹、destructive→墨
    assert "[data-dashboard-segmented-meter='true'] > span.bg-emerald-500" in css
    assert "[data-dashboard-segmented-meter='true'] > span.bg-destructive" in css
    # 状态灯：方形无辉光，error 不用红
    assert "[data-status-light='true'][data-status='error']" in css
    assert "box-shadow: none !important" in css
    # 统计告警色改墨
    assert "--stats-alert: var(--ef-ink)" in css


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
    assert "[data-dashboard-toast='true'][data-state='open']" in css
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
    asyncio.run(plugin.on_config_update("self", {}, "0.4.2"))
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
    asyncio.run(plugin.on_config_update("self", cfg, "0.4.2"))
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


# ---------------------------------------------------------------- 麦麦观察首页覆盖

def test_preamble_board_tokens(module):
    """首页看板层 token 必须补齐：--board-*/--surface-*/--chat-* 全部 !important。

    反向验证：首页（ObservationHome）走独立 --board-* 层，此前只覆盖
    --color-* 导致「麦麦观察页没动」。删掉任一组覆盖即失败。
    """
    v = module.resolve("lime", "neutral", "compact")
    pre = module.build_preamble(v)
    for token in (
        "--board-module-radius:0px !important",
        "--board-module-shadow:none !important",
        "--board-number-font:",
        "--surface-radius:0px !important",
        "--surface-data-texture:none !important",
        "--list-selected-bg:var(--ef-accent) !important",
        "--chat-bubble-radius:0px !important",
        "--obs-heading-font:",
    ):
        assert token in pre, f"缺首页 token 覆盖 {token}"
    # 图表色：系列 1=强调色，不用红绿；深浅两套都覆盖
    assert f"--board-chart-1:{v['accentHex']} !important" in pre
    light_block, dark_block = pre.split("html.dark{")
    assert "--board-accent:var(--ef-ink) !important" in light_block, "浅色看板强调=墨"
    assert "--board-accent:var(--ef-accent) !important" in dark_block, "深色看板强调=强调色"


def test_css_board_home_parts():
    """首页部件皮肤：看板页签/代号/周期拨杆/输入条/桌宠/会话列表。"""
    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    # 看板模块：直角细线 + 顶边粗墨页签（scaleX 0.14 → hover 伸开）
    assert "[data-board-module='true']::before" in css
    assert "scaleX(0.14)" in css
    # 英文代号：三风格统一显示 + // 前缀 + 宽体
    assert "[data-board-module-code='true']" in css
    assert "display: inline !important" in css or "display:inline!important" in css
    assert "content: '// '" in css or "content:'// '" in css
    # 周期拨杆 / 输入条 / 桌宠 / 会话列表（真机属性名，源码核对）
    for sel in (
        "[data-observation-period='true']",
        "[data-observation-period-thumb='true']",
        "[data-observation-composer='true']",
        "[data-desktop-pet-bubble='true']",
        "[data-conversation-item='true']",
    ):
        assert sel in css, f"缺首页部件选择器 {sel}"


def test_css_no_red_green_status():
    """状态色不用红绿：原生绿（hsl(152…)/#22c55e/--m-ok）不得残留为状态色。

    反向验证：ask 模式灯/发送键、图标轨描边、功能状态灯曾是绿色。
    """
    import re

    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    # 只查声明区（注释里引用原生值作说明是允许的）
    decls = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert "hsl(152" not in decls, "ask 模式绿残留"
    assert "#22c55e" not in decls, "图标轨绿描边残留"
    assert "var(--m-ok)" not in decls, "不得引用移动端绿点变量"
    # 覆盖规则本身必须存在（方形 + 强调色）
    assert "[data-dashboard-shell='true'] [data-dashboard-feature-status-light='true']" in css
    assert "[data-observation-mode-lamp='true']" in css


def test_css_real_selectors_only():
    """选择器必须与 dashboard 1.10.8 真实属性一致，失效选择器不得残留。"""
    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    for dead in (
        "data-sonner-toast",
        "data-radix-slider",
        "data-mobile-tab-bar",
        "data-slot='card'",
        "data-slot='input'",
        "data-radix-select-trigger",
    ):
        assert dead not in css, f"失效选择器残留：{dead}"
    for real in (
        "data-dashboard-toast='true'",
        "data-dashboard-slider-thumb='true'",
        "data-mobile-tabbar='true'",
        "data-dashboard-input='true'",
        "data-dashboard-select-trigger='true'",
    ):
        assert real in css, f"缺真实选择器：{real}"
    # 玻璃/循环装饰动画必须被压掉
    assert "backdrop-filter: none !important" in css
    assert ".animate-ping" in css and ".animate-bounce" in css
    assert ".m-glass" in css


def test_css_assets_exist_and_nonempty():
    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    assert "clip-path" in css, "切角语法缺失"
    assert "prefers-reduced-motion" in css, "缺减少动态效果保护"
    assert "--ef-accent" in css
    fonts = (PLUGIN_DIR / "theme" / "fonts.css").read_text(encoding="utf-8")
    assert "font-stretch: 50% 125%" in fonts, "Saira 可变宽度轴声明缺失"


# ---------------------------------------------------------------- 0.4.0 六维变体

def test_resolve_six_dims_defaults(module):
    """新三维默认值=现状：0.3.0 用户升级后外观零变化。"""
    v = module.resolve("lime", "neutral", "compact")
    assert v["cut"] == "standard" and v["cutK"] == 1.0
    assert v["ground"] == "contours"
    assert v["motion"] == "full"
    # 默认切角数值与 0.3.0 硬编码一致
    pre = module.build_preamble(v)
    assert "--ef-cut-sm:7px" in pre
    assert "--ef-cut-btn:8px" in pre
    assert "--ef-cut-panel:26px" in pre


def test_resolve_cut_scaling(module):
    """cut 三档缩放切角：tight ×0.6 / standard ×1 / wide ×1.6。"""
    tight = module.build_preamble(module.resolve("lime", "neutral", "compact", cut="tight"))
    wide = module.build_preamble(module.resolve("lime", "neutral", "compact", cut="wide"))
    assert "--ef-cut-k:0.6" in tight
    assert "--ef-cut-sm:4.2px" in tight
    assert "--ef-cut-k:1.6" in wide
    assert "--ef-cut-sm:11.2px" in wide
    assert "--ef-cut-panel:41.6px" in wide


def test_resolve_invalid_new_dims_fall_back(module):
    v = module.resolve("lime", "neutral", "compact", cut="huge", ground="dots", motion="wild")
    assert v["cut"] == "standard"
    assert v["ground"] == "contours"
    assert v["motion"] == "full"


def test_variant_attrs(module):
    """html 属性只带 ground/motion（cut 走 CSS 变量，不需要属性）。"""
    v = module.resolve("lime", "neutral", "compact", ground="grid", motion="calm")
    attrs = module.variant_attrs(v)
    assert 'data-ef-ground="grid"' in attrs
    assert 'data-ef-motion="calm"' in attrs
    assert "data-ef-cut" not in attrs


def test_css_ground_variants():
    """ground 四态：contours 默认 / grid 网格 / hatch 斜线纹 / plain 无。"""
    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    assert "html[data-ef-ground='grid'] [data-observation-shell='true']::before" in css
    assert "html[data-ef-ground='hatch'] [data-observation-shell='true']::before" in css
    assert "html[data-ef-ground='plain'] [data-observation-shell='true']::before" in css
    assert "3rem 3rem" in css, "grid 网格间距"
    assert "var(--ef-hatch)" in css, "hatch 斜线纹变量"
    assert "display: none" in css.split("data-ef-ground='plain'")[1][:200], "plain 应隐藏底纹"
    # hatch 变量由 preamble 提供
    from importlib import import_module
    ev = import_module("endfield_theme.et_variants")
    pre = ev.build_preamble(ev.resolve("lime", "neutral", "compact"))
    assert "--ef-hatch:repeating-linear-gradient(-45deg" in pre


def test_css_motion_calm():
    """motion=calm：压掉入场动画，保留退出与回应。"""
    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    assert "html[data-ef-motion='calm'] [role='dialog'][data-state='open']" in css
    assert "html[data-ef-motion='calm'] [data-dashboard-toast='true'][data-state='open']" in css
    assert "html[data-ef-motion='calm'] [role='tabpanel'][data-state='active']" in css
    # calm 块只压 open/active（入场），不压 closed（退出）
    calm_block = css.split("html[data-ef-motion='calm']")[1].split("@media (prefers-reduced-motion: reduce)")[0]
    assert "data-state='closed'" not in calm_block, "calm 不应压退出动画"


def test_config_schema_six_dims(module):
    """配置页六开关中文化齐全（含新三维的 label/hint/choice 双语）。"""
    from maibot_sdk.config import generate_plugin_config_schema

    schema = generate_plugin_config_schema(module.EndfieldThemeConfig)
    fields = schema["sections"]["appearance"]["fields"]
    expected = {
        "cut": ("切角幅度", {"tight": "收紧（×0.6）", "standard": "标准（×1）", "wide": "放宽（×1.6）"}),
        "ground": ("底纹", {"contours": "等高线", "grid": "网格", "hatch": "斜线纹", "plain": "无"}),
        "motion": ("动效", {"full": "全开", "calm": "平静"}),
    }
    for name, (label, choices) in expected.items():
        field = fields[name]
        assert field["label"] == label, f"{name} 标签未中文化"
        zh = field["i18n"]["zh-CN"]
        assert zh["label"] == label
        assert zh.get("hint"), f"{name} 缺 hint"
        for choice, text in choices.items():
            assert zh[f"choice:{choice}"] == text, f"{name}/{choice} 中文显示名不符"
            assert field["i18n"]["en-US"][f"choice:{choice}"], f"{name}/{choice} 缺英文对照"


# ---------------------------------------------------------------- 0.4.0 官方风格让位

def test_stylegate_all_rules_gated(module):
    """让位门控：每条规则选择器都带 millennium/future-retro 排除。

    反向验证：漏掉任何一条规则，千禧/复古下主题就会部分生效。
    """
    import re
    from importlib import import_module
    sg = import_module("endfield_theme.et_stylegate")

    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    gated = sg.gate_css(css)

    def scan_rules(text):
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        out, i, n = [], 0, len(text)
        while i < n:
            brace = text.find("{", i)
            if brace < 0:
                break
            head = text[i:brace].strip()
            depth, j = 1, brace + 1
            while j < n and depth:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                j += 1
            is_skip = bool(re.match(r"@(keyframes|-webkit-keyframes|font-face|property)", head, re.I))
            is_cond = bool(re.match(r"@(media|supports|container|layer)", head, re.I))
            if is_skip:
                i = j
                continue
            if is_cond:
                out.extend(scan_rules(text[brace + 1:j - 1]))
            elif head and not head.startswith("@"):
                out.append(head)
            i = j
        return out

    heads = scan_rules(gated)
    assert len(heads) > 150, "规则数异常，扫描器可能失效"
    for h in heads:
        for part in h.split(","):
            assert sg.GATE in part, f"漏网选择器：{part.strip()[:70]}"
    # 声明体逐字节不变（门控只动选择器）
    bodies = lambda t: re.findall(r"\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", t, flags=re.S))
    assert bodies(css) == bodies(gated), "门控改动了声明体"
    # keyframes 保留（引用它们的规则已被门控）
    assert "@keyframes ef-power-on" in gated


def test_stylegate_preamble_gated(module):
    from importlib import import_module
    sg = import_module("endfield_theme.et_stylegate")
    pre = sg.gate_preamble(module.build_preamble(module.resolve("lime", "neutral", "compact")))
    assert "html" + sg.GATE + "{" in pre
    assert "html.dark" + sg.GATE + "{" in pre
    assert pre.count(sg.GATE) == 2


def test_injected_style_gated(env):
    """注入产物整体门控：千禧/复古下 100% 官方原样。"""
    plugin, dist = env
    _apply(plugin)
    html = (dist / "index.html").read_text(encoding="utf-8")
    from importlib import import_module
    sg = import_module("endfield_theme.et_stylegate")
    style = html.split('id="endfield-theme-style"')[1].split("</style>")[0]
    assert sg.GATE in style
    assert "html" + sg.GATE + "{" in style, "preamble 未门控"
    # 字体声明（@font-face）跳过门控是允许的——字体无副作用
    assert "@font-face" in style


# ---------------------------------------------------------------- 0.4.0 JS 反馈层

def test_fx_js_exists_and_syntax():
    """fx.js 存在、非空、node 语法检查通过（若 node 可用）。"""
    import shutil
    import subprocess

    fx = PLUGIN_DIR / "theme" / "endfield-fx.js"
    assert fx.is_file() and fx.stat().st_size > 3000
    src = fx.read_text(encoding="utf-8")
    # 操作反馈四件套都在
    assert "flashDone" in src
    assert "ef-is-done" in src
    assert "ghostWipeOut" in src
    assert "flipFrozen" in src or "frozenRows" in src
    assert "startViewTransition" in src
    # 静止条件齐全
    assert "prefers-reduced-motion: reduce" in src
    assert "efMotion === 'calm'" in src or 'efMotion === "calm"' in src
    assert "millennium" in src and "future-retro" in src
    assert "no-animations" in src
    # 展示页语法不进后台
    assert "scramble" not in src, "乱码落定不应进后台"
    assert "wireParallax" not in src, "指针视差不应进后台"
    assert "wireReadouts" not in src
    node = shutil.which("node")
    if node:
        r = subprocess.run([node, "--check", str(fx)], capture_output=True, text=True)
        assert r.returncode == 0, f"fx.js 语法错误：{r.stderr}"


def test_fx_injected_and_removed(env):
    """JS 注入-移除闭环：script 标签 + 资产分发 + 卸载清理。"""
    plugin, dist = env
    _apply(plugin)
    html = (dist / "index.html").read_text(encoding="utf-8")
    assert 'id="endfield-theme-fx"' in html
    assert html.count('id="endfield-theme-fx"') == 1
    assert 'src="/fonts/endfield/endfield-fx.js"' in html
    assert "defer" in html.split('id="endfield-theme-fx"')[1].split(">")[0]
    fx_dist = dist / "fonts" / "endfield" / "endfield-fx.js"
    assert fx_dist.is_file()
    assert fx_dist.read_bytes() == (PLUGIN_DIR / "theme" / "endfield-fx.js").read_bytes()
    # 幂等
    _apply(plugin)
    assert (dist / "index.html").read_text(encoding="utf-8") == html
    # 卸载还原
    asyncio.run(plugin.on_unload())
    assert (dist / "index.html").read_text(encoding="utf-8") == OFFICIAL_HTML
    assert not (dist / "fonts" / "endfield").exists()


def test_html_variant_attrs_lifecycle(env):
    """ground/motion 属性写进 <html>，热更新换值，卸载摘除。"""
    plugin, dist = env
    _apply(plugin)
    html = (dist / "index.html").read_text(encoding="utf-8")
    assert 'data-ef-ground="contours"' in html
    assert 'data-ef-motion="full"' in html
    # 属性在 <html> 标签上，不在别处
    import re
    tag = re.search(r"<html\b[^>]*>", html).group(0)
    assert "data-ef-ground" in tag
    # 热更新换 ground/motion
    _set_config(plugin, ground="grid", motion="calm")
    asyncio.run(plugin.on_config_update("self", {}, "0.4.2"))
    html2 = (dist / "index.html").read_text(encoding="utf-8")
    assert 'data-ef-ground="grid"' in html2
    assert 'data-ef-motion="calm"' in html2
    assert 'data-ef-ground="contours"' not in html2, "旧 ground 值残留"
    tag2 = re.search(r"<html\b[^>]*>", html2).group(0)
    assert tag2.count("data-ef-ground") == 1, "html 标签上 ground 属性重复"
    assert tag2.count("data-ef-motion") == 1
    # 卸载摘除
    asyncio.run(plugin.on_unload())
    html3 = (dist / "index.html").read_text(encoding="utf-8")
    assert html3 == OFFICIAL_HTML
    assert "data-ef-" not in html3


def test_css_js_feedback_parts():
    """JS 配套 CSS：完成黄穿 / 删行擦出 / view-transition 层抑制。"""
    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    assert "@keyframes ef-done" in css
    assert ".dashboard-button--default.ef-is-done::before" in css
    assert "translateX(101%)" in css, "黄穿应穿过按钮右侧"
    assert ".ef-out-wipe" in css
    assert "html.ef-theming::view-transition-old(root)" in css
    assert "html.ef-theming::view-transition-new(root)" in css
    assert "::view-transition-old(root)" in css


def test_default_appearance_unchanged(env):
    """默认配置注入产物 = 0.3.0 语义：cut×1 / contours / full，外观零变化。"""
    plugin, dist = env
    _apply(plugin)
    html = (dist / "index.html").read_text(encoding="utf-8")
    assert "--ef-cut-k:1.0" in html
    assert "--ef-cut-sm:7px" in html
    assert 'data-ef-ground="contours"' in html
    assert 'data-ef-motion="full"' in html
    # ground 变体规则存在但默认不激活（contours 无属性选择器分支）
    assert "html[data-ef-ground='grid']" in html


# ---------------------------------------------------------------- 0.4.2 浅色侧栏会话可读性

def test_css_sidebar_conversation_light_readable():
    """浅色侧栏会话名称必须可读（真机反馈「浅色时左侧变化不完全」）。

    根因：原生 conversation.css 给条目设 color:var(--surface-ink)，
    本主题 preamble 把 --surface-ink 压成 --ef-ink（浅色=墨），
    侧栏恒深色命令栏 → 浅色模式墨字墨底，名称整片消失。
    反向验证：删掉条目强制浅字规则即失败。
    """
    import re

    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    decls = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # 条目本体强制浅字（不跟 --surface-ink 走）
    m = re.search(r"\[data-conversation-item='true'\]\s*\{([^}]*)\}", decls)
    assert m, "缺会话条目规则"
    assert "color: #EDEDED !important" in m.group(1), "条目未强制浅字，浅色会墨字墨底"
    # 名称继承条目浅字
    assert "[data-conversation-item-heading='true'] strong" in decls
    # 非选中预览/状态用命令栏灰
    assert "[data-conversation-item='true']:not([data-selected='true']) [data-conversation-item-preview='true']" in decls
    # 选中态预览/状态转墨色半透明（强调色底上可读）
    assert "[data-conversation-item='true'][data-selected='true'] [data-conversation-item-preview='true']" in decls
    assert "rgba(22, 22, 22, 0.72)" in decls
    # 悬停命令栏深灰底（原生 --list-hover-bg 浅色翻车）
    assert "[data-conversation-item='true']:not([data-selected='true']):hover" in decls
    # 折叠态条目浅字 + 堆叠头像边改命令栏底色
    assert "[data-observation-sidebar='true'][data-collapsed='true'] [data-conversation-item='true'][data-selected='true']" in decls
    assert "[data-observation-stack-avatar='true'] > [data-conversation-avatar='true']" in decls
    assert "border-color: var(--ef-command-bar) !important" in decls


def test_sidebar_conversation_color_not_surface_ink(env):
    """注入产物里会话条目颜色不得依赖 --surface-ink（浅色=墨会翻车）。"""
    plugin, dist = env
    _apply(plugin)
    html = (dist / "index.html").read_text(encoding="utf-8")
    style = html.split('id="endfield-theme-style"')[1].split("</style>")[0]
    import re
    # 条目规则块内必须是硬浅字，不是 var(--surface-ink)/var(--ef-ink)
    m = re.search(r"\[data-conversation-item='true'\]\s*\{([^}]*)\}", style)
    assert m
    body = m.group(1)
    assert "#EDEDED" in body
    assert "--surface-ink" not in body and "var(--ef-ink)" not in body


# ---------------------------------------------------------------- 0.4.2 图表提示框可读性

def test_css_chart_tooltip_text_not_series_color():
    """图表提示框文字不得沿用系列色（真机反馈「浅色模式下黄色字体看不清」）。

    根因：recharts DefaultTooltipContent 把 entry.color（= 柱子 fill）写成
    <li>/<span> 的**行内 color**，行内样式压过容器 color。
    本主题 --board-chart-1 = 强调色，浅色 tooltip 底是白板 →
    「输入」行黄字压白板 1.11:1，完全看不见；
    「输出」行是墨 45% 合成灰 2.95:1，同样不达 AA。
    图表色是填充语义，名称/数值必须回到墨与次要墨。
    反向验证：删掉这组规则即失败。
    """
    import re

    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    decls = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    # 行本体与数值：墨
    m = re.search(r"\.recharts-tooltip-item,\s*([\s\S]*?)\{([^}]*)\}", decls)
    assert m, "缺 tooltip 行文字规则"
    head, body = m.group(1), m.group(2)
    for cls in (
        ".recharts-tooltip-item-name",
        ".recharts-tooltip-item-separator",
        ".recharts-tooltip-item-value",
        ".recharts-tooltip-item-unit",
        ".recharts-tooltip-label",
        ".recharts-legend-item-text",
    ):
        assert cls in head, f"{cls} 未纳入行内 color 覆盖"
    assert "color: var(--ef-ink) !important" in body

    # 名称与图例文字：次要墨
    m2 = re.search(
        r"\.recharts-tooltip-item-name,\s*\.recharts-legend-item-text\s*\{([^}]*)\}", decls
    )
    assert m2, "缺名称/图例次要墨规则"
    assert "color: var(--ef-ink2) !important" in m2.group(1)

    # 数值等宽数字（语法：计数一律 tabular）
    assert "font-variant-numeric: tabular-nums" in decls


def test_chart_tooltip_contrast_both_modes():
    """按 WCAG 复算：修复后 tooltip 文字在浅/深两套底上都达 AA。

    这条断言算的是**修复后**的实际色对，不是复制源码里的数字。
    """
    def lin(v):
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def lum(rgb):
        return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])

    def hx(h):
        h = h.lstrip("#")
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]

    def ratio(a, b):
        la, lb = lum(hx(a)), lum(hx(b))
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    # 浅色：板 #FFFFFF；深色：板 #222222（preamble 的 --ef-panel）
    assert ratio("#161616", "#FFFFFF") >= 4.5   # 数值/标签
    assert ratio("#5C5C5C", "#FFFFFF") >= 4.5   # 名称
    assert ratio("#EDEDED", "#222222") >= 4.5
    assert ratio("#A3A3A3", "#222222") >= 4.5
    # 反面对照：修复前的两种写法都不达标（证明这条修复不是可选的美化）
    assert ratio("#FFFA00", "#FFFFFF") < 3      # 黄字压白板，1.11:1
    # 墨 45% 合成在白板上 = #969696
    assert ratio("#969696", "#FFFFFF") < 4.5


def test_success_icon_light_uses_ink():
    """成功图标（原生 text-green-500）浅色必须用墨：黄图标压白板 1.11:1 < 3:1 图标门槛。"""
    import re

    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    decls = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    m = re.search(r"(?<![\w.])\.text-green-500\s*\{([^}]*)\}", decls)
    assert m, "缺成功图标规则"
    assert "color: var(--ef-ink) !important" in m.group(1), "浅色成功图标仍用强调色，浅底上看不见"
    m2 = re.search(r"html\.dark \.text-green-500\s*\{([^}]*)\}", decls)
    assert m2, "深色成功图标未单独声明"
    assert "color: var(--ef-accent) !important" in m2.group(1)


def test_tooltip_rules_survive_stylegate(env):
    """门控后 tooltip 规则仍在，且带官方风格让位前缀（切千禧/复古时不生效）。"""
    plugin, dist = env
    _apply(plugin)
    html = (dist / "index.html").read_text(encoding="utf-8")
    style = html.split('id="endfield-theme-style"')[1].split("</style>")[0]
    assert ".recharts-tooltip-item-value" in style
    gate = ":not([data-dashboard-style='millennium']):not([data-dashboard-style='future-retro'])"
    # 选择器列表里每一条分支都必须带门控前缀（注释可能紧贴在选择器前，故不按行取）
    import re
    m = re.search(r"(?:html[^\n{}]*?)?\.recharts-tooltip-item,[\s\S]*?\{", style)
    assert m, "产物里找不到 tooltip 规则"
    branches = [b.strip() for b in m.group(0).rstrip("{").split(",")]
    assert len(branches) >= 7, f"tooltip 选择器分支数异常：{len(branches)}"
    for b in branches:
        # 首条分支前可能粘着注释尾，只校验门控串存在
        assert gate in b, f"分支未门控：{b[:80]}"


# ---- 0.4.3 加载动效：按角色分流，不再无差别铺斜线纹 ----

def _decls():
    import re
    css = (PLUGIN_DIR / "theme" / "endfield-theme.css").read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_pulse_no_longer_blanket_striped():
    """裸 .animate-pulse 只能停动画，不能再带 background 斜线纹。

    反向验证：把 0.4.2 那条无差别铺纹规则改回来，这条立刻红。
    """
    import re
    d = _decls()
    m = re.search(r"(?<![\w.:/-])\.animate-pulse\s*\{([^}]*)\}", d)
    assert m, "缺 .animate-pulse 基础规则"
    body = m.group(1)
    assert "animation: none !important" in body, "原生脉冲未停（语法禁发光脉冲）"
    assert "repeating-linear-gradient" not in body, (
        "裸 .animate-pulse 仍铺斜线纹：6px 状态点会掉到 1.10:1 而失显"
    )
    assert "background" not in body, "裸 .animate-pulse 不应声明任何 background"


def test_skeleton_only_striped_by_placeholder_class():
    """斜线纹只给真空骨架（bg-primary/10 与 bg-muted 占位特征）。"""
    import re
    d = _decls()
    m = re.search(
        r"\.animate-pulse\.bg-primary\\/10,\s*([\s\S]*?)\{([^}]*)\}", d
    )
    assert m, "找不到限定后的骨架铺纹规则"
    head = ".animate-pulse.bg-primary\\/10," + m.group(1)
    assert ".animate-pulse.bg-muted" in head
    assert "repeating-linear-gradient" in m.group(2)


def test_status_dot_solid_and_stepped():
    """6px 状态点：实心墨/黄 + 步进硬亮关键帧，且排除装饰光晕。"""
    import re
    d = _decls()
    sel = r"\.animate-pulse\.rounded-full:not\(\[class\*='blur'\]\)"
    m = re.search(sel + r"\s*\{([^}]*)\}", d)
    assert m, "缺状态点实心规则"
    assert "background: var(--ef-ink) !important" in m.group(1)
    assert "repeating-linear-gradient" not in m.group(1), "状态点仍被铺纹"
    m2 = re.search(r"html\.dark " + sel + r"\s*\{([^}]*)\}", d)
    assert m2 and "var(--ef-accent)" in m2.group(1), "深色状态点未用强调色"
    # 步进关键帧：只有硬切档位，没有中间缓动值
    kf = re.search(r"@keyframes ef-dot-step\s*\{([\s\S]*?)\n\}", d)
    assert kf, "缺 ef-dot-step 关键帧"
    assert "steps(1, end)" in d, "状态点动画未用 steps 硬切"
    # 装饰光晕（MessageList.tsx:84 blur-xl）必须消失，而不是变成实心块
    m3 = re.search(r"\.animate-pulse\[class\*='blur'\]\s*\{([^}]*)\}", d)
    assert m3 and "display: none !important" in m3.group(1), "发光光晕未关掉"


def test_svg_spinner_taken_over():
    """全站 svg.animate-spin 必须被接管（0.4.2 只命中 setup 的 border 环）。"""
    import re
    d = _decls()
    m = re.search(r"(?<![\w.-])svg\.animate-spin\s*\{([^}]*)\}", d)
    assert m, "缺 svg.animate-spin 颜色接管"
    assert "color: var(--ef-ink) !important" in m.group(1)
    m2 = re.search(r"html\.dark svg\.animate-spin\s*\{([^}]*)\}", d)
    assert m2 and "var(--ef-accent)" in m2.group(1)
    assert re.search(r"svg\.animate-spin\s*\{\s*animation: ef-spin-step[^}]*steps\(8, end\)", d), (
        "SVG 转圈未改机械 8 格步进"
    )


def test_content_card_not_striped():
    """有内容的状态卡（border-amber-500 animate-pulse）：不铺纹，改左侧竖条。"""
    import re
    d = _decls()
    m = re.search(r"\.animate-pulse\.border-amber-500\s*\{([^}]*)\}", d)
    assert m, "缺状态卡规则"
    body = m.group(1)
    assert "background: none !important" in body, "状态卡内容仍被斜纹压住"
    assert "border-inline-start: 3px solid var(--ef-ink) !important" in body
    # SVG 图标 busy 也不铺纹
    m2 = re.search(r"svg\.animate-pulse\s*\{([^}]*)\}", d)
    assert m2 and "background: none !important" in m2.group(1)


def test_restart_big_spinner_becomes_bar():
    """重启遮罩 64px 转圈换成横走黄格（skill：正在处理不放转圈）。"""
    import re
    d = _decls()
    m = re.search(r"svg\.animate-spin\.h-16\s*\{([^}]*)\}", d)
    assert m, "缺重启遮罩大指示规则"
    body = m.group(1)
    assert "background-image" in body and "var(--ef-accent)" in body
    assert "color: transparent !important" in body, "转圈线条未藏掉"
    assert re.search(
        r"svg\.animate-spin\.h-16\s*\{\s*animation: ef-indeterminate-bg", d
    ), "大指示未改成黄格横走（仍在转圈）"
    kf = re.search(r"@keyframes ef-indeterminate-bg\s*\{([\s\S]*?)\n\}", d)
    assert kf and "background-position" in kf.group(1)


def test_progress_segmented_24_steps():
    """进度条按格跳：24 格 + steps(24)，用官方稳定钩子而非哈希类名。"""
    import re
    d = _decls()
    m = re.search(r"\[data-dashboard-progress='true'\]\s*\{([^}]*)\}", d)
    assert m, "缺分段进度条轨道规则"
    assert "100% / 24" in m.group(1), "格数不是 24"
    m2 = re.search(
        r"\[data-dashboard-progress-indicator='true'\]\s*\{([^}]*)\}", d
    )
    assert m2 and "steps(24, end)" in m2.group(1), "进度未按格跳（仍平滑滑动）"
    assert "var(--ef-accent)" in m2.group(1)


def test_loading_contrast_both_modes():
    """加载态图形对比度复算：修复后 ≥3:1，修复前不达标（反面对照）。

    算的是修复后的真实色对；6px 斜纹覆盖率 21.5% 由几何积分得出（见 CHANGELOG）。
    """
    def lin(v):
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def lum(p):
        return 0.2126 * lin(p[0]) + 0.7152 * lin(p[1]) + 0.0722 * lin(p[2])

    def hx(h):
        h = h.lstrip("#")
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]

    def ratio(a, b):
        la, lb = lum(hx(a)), lum(hx(b))
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    def mix(fg, alpha, bg):
        f, b = hx(fg), hx(bg)
        return "#%02X%02X%02X" % tuple(
            round(x * alpha + y * (1 - alpha)) for x, y in zip(f, b)
        )

    # 修复后：实心墨点压白纸 / 实心黄点压深板
    assert ratio("#161616", "#FFFFFF") >= 3
    assert ratio("#FFFA00", "#222222") >= 3
    # 反面对照：0.4.2 的 6px 斜纹点（ink 22% 再乘 21.5% 覆盖率）
    stripe = mix("#161616", 0.22, "#FFFFFF")
    effective = mix(stripe, 0.215, "#FFFFFF")
    assert ratio(effective, "#FFFFFF") < 3, "反面对照失效：斜纹小点本应不达标"
    assert ratio(effective, "#FFFFFF") < 1.5, "斜纹小点实测约 1.10:1"


def test_loading_rules_survive_stylegate(env):
    """门控后加载态规则逐分支仍带官方风格让位前缀。"""
    import re
    plugin, dist = env
    _apply(plugin)
    html = (dist / "index.html").read_text(encoding="utf-8")
    style = html.split('id="endfield-theme-style"')[1].split("</style>")[0]
    gate = ":not([data-dashboard-style='millennium']):not([data-dashboard-style='future-retro'])"
    for key in (
        ".animate-pulse.rounded-full",
        "svg.animate-spin",
        ".animate-pulse.border-amber-500",
        "[data-dashboard-progress='true']",
    ):
        assert key in style, f"产物里缺 {key}"
        idx = style.index(key)
        # 取该规则所在的选择器列表（回退到上一个 } 或 { 之后）
        start = max(style.rfind("}", 0, idx), style.rfind("{", 0, idx)) + 1
        end = style.index("{", idx)
        for b in style[start:end].split(","):
            assert gate in b, f"{key} 分支未门控：{b.strip()[:90]}"
