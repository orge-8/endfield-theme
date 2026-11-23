# -*- coding: utf-8 -*-
"""插件自定义 WebUI 页面适配守护用例 —— **可直接抄的通用模板**。

★ 自包含：不依赖任何插件仓库。把本文件放进你的 tests/，改下面「配置区」几行即可。
  跑法：pytest tests/test_page_adaptation.py

这些断言不是凭空设计的，每一条都对应一个**真实踩过的坑**（见各用例 docstring）。
它们守护的是「适配做对了」而不是「代码能跑」——后者由你原有的功能测试负责。

--------------------------------------------------------------------------
配置区：只改这里
--------------------------------------------------------------------------
"""
from __future__ import annotations

import pathlib
import re

import pytest

# 插件根目录（本文件在 tests/ 下，故取 parent.parent）
PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent

# 你的自定义页面文件名（不含 .html），按 webui/ 下的实际文件填。
# 单页插件就填一个；多页插件全列上，跨页一致性断言才有意义。
PAGES = ("main",)

# 页面所在子目录
WEBUI_DIR = "webui"

# 你自己的圆角别名。没有别名、直接用宿主令牌就填 "--maibot-radius"。
# 多个别名都列上，负圆角断言会逐个检查。
ROUND_TOKENS = ("--maibot-radius",)

# 派生圆角（max(0px, calc(...))）的**预期总数**。
# 填 None 表示不校验数量（只校验「没有未钳住的」）。
# 建议填确切数字：数量变化说明有人加了新的派生圆角，应当被 review。
EXPECTED_CLAMPED_COUNT = None

# 语义圆点选择器（状态灯 / 进度点这类「它就是一个点」的元素）。
# 这些的 50% 必须保留，门控层不许压平。没有就留空元组。
SEMANTIC_DOTS = ()

# **写死装饰圆角**的选择器（999px 胶囊、写死 px 的图标底板等）。
# 这些必须在门控层里被压成直角，否则方角主题下它们仍是圆的。
# 走 var(--maibot-radius) 的**不要**列进来（那种本来就跟随，无需门控）。
# 没有就留空元组，对应用例会跳过。
HARDCODED_ROUND = ()

# 既有的**真生效**焦点环选择器（带 !important 的那条）。
# 没有就填 None —— 那么断言会要求「不许有死焦点环」。
REAL_FOCUS_RING = None

# 允许存在的宿主类。路线二通常只允许根容器的 maibot-page；
# 完全不用宿主类就填 ()。路线一请把用到的组件类都列进来。
ALLOWED_HOST_CLASSES = ("maibot-page",)

# 走**路线一**（全面接受宿主组件观感）时置 True：
# 此时放行所有 maibot-* 类（含 maibot-button-primary / maibot-card-header 这类变体），
# 免得手工枚举漏一个就红。路线二保持 False —— 那条断言正是防止你不小心加了类。
ROUTE_ONE = False

# 探测段与门控层的定位锚点（用于跨页逐字节比对）。
# 用你代码里真实存在的注释或语句片段；单页插件可忽略。
PROBE_START = "方角主题能力探测"
PROBE_END = "document.fonts.ready"
GATE_START = "方角主题跟随层"

# 门控属性（与探测脚本里 setAttribute 的名字一致）
GATE = "html[data-ef-page='on']"

# --------------------------------------------------------------------------
# 以下一般不用改
# --------------------------------------------------------------------------

CONTROL_CLASSES = (
    "button", "card", "input", "select", "badge", "table", "inset", "number", "muted",
)


def _html(page: str) -> str:
    return (PLUGIN_DIR / WEBUI_DIR / f"{page}.html").read_text(encoding="utf-8")


def _style(page: str) -> str:
    return _html(page).split("</style>")[0]


def _code(page: str) -> str:
    """剥掉 HTML/CSS/JS 注释后的代码。

    ★ 判「有没有用某写法」必须先剥注释，否则解释性注释会被判成违规。
      实测踩过两次：① 注释里写「不要读 prefers-color-scheme」被自己的用例报错；
      ② 片段注释里的反面示范 ``✗ border-radius: calc(var(--round) - 3px)``
        被负圆角用例判成真违规。
    """
    text = _html(page)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?<![:\w])//[^\n]*", "", text)


def _rules(css: str):
    """产出 (选择器, 声明文本)。跨行、多声明都能处理；先剥注释。

    ★ 按「规则」而不是按「行」判断，才能区分
      「门控层把圆点压平了」和「门控层给圆点加了动画」——
      后者完全合法，按行匹配类名会误报。
    """
    plain = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", plain):
        sel = " ".join(m.group(1).split())
        if not sel or sel.startswith("@"):
            continue
        yield sel, m.group(2)


def test_pages_exist():
    """配置区列的页面必须真在磁盘上（防文件名改了配置没跟着改）。"""
    for page in PAGES:
        path = PLUGIN_DIR / WEBUI_DIR / f"{page}.html"
        assert path.is_file(), f"配置的页面不存在: {path}"
        assert path.read_text(encoding="utf-8").strip(), f"{page}.html 是空文件"


def test_radius_calc_never_goes_negative():
    """★ 派生圆角必须钳住下界。

    ``calc(var(--round) - Npx)`` 在圆角令牌归零时算出负值。
    ``border-radius`` **不继承**，非法值使整条声明被丢弃后取**初始值 0**
    ⇒ 在方角主题下**碰巧仍是方角**，所以这是**隐患不是现症**；
    真正出问题的是令牌为小正值时（如 2px - 4px），层级差静默消失。

    不管哪种情况都要钳：「靠非法值恰好得到想要的结果」不是设计。
    """
    total = 0
    for page in PAGES:
        # ★ 必须剥注释：文档/片段里常有「✗ 不要这样写」的反面示范，
        #   扫全文会把注释里的示范判成违规代码。实测踩过（route2-shape.css
        #   第 3 段的反面示范触发了本用例）。
        html = _code(page)
        for token in ROUND_TOKENS:
            bare = re.escape(f"calc(var({token})")
            assert not re.search(rf"border-radius:\s*{bare}\s*-", html), (
                f"{page}.html 仍有未钳住的负值 calc（令牌 {token}）"
            )
            total += len(re.findall(
                rf"max\(0px,\s*calc\(var\({re.escape(token)}\)", html))
    if EXPECTED_CLAMPED_COUNT is not None:
        assert total == EXPECTED_CLAMPED_COUNT, (
            f"派生圆角数量应为 {EXPECTED_CLAMPED_COUNT}，实际 {total}；"
            "新增派生圆角请一并 review 并更新配置区"
        )


def test_shape_layer_is_fully_gated():
    """★ 形状跟随层每条直角声明都必须带门控。

    没门控 ⇒ 没装主题时页面也变方 ⇒ 违反「未装主题外观不变」。

    按**规则**判断而不是按行：多行选择器组
    ``html[gate] .a,\\nhtml[gate] .b { border-radius: 0 }``
    按行扫会在声明行上找不到门控前缀而误报。
    """
    for page in PAGES:
        style = _style(page)
        assert GATE in style, f"{page}.html 缺少形状跟随层门控"
        for sel, body in _rules(style):
            if not re.search(r"border-radius\s*:\s*0(?:px)?\s*(?:;|$)", body.strip()):
                continue
            assert GATE in sel, (
                f"{page}.html 直角声明没门控: {sel} {{{body.strip()[:80]}}}"
            )


def test_no_new_host_control_classes():
    """★ 不得新增宿主控件类（路线二）；允许的类必须在配置区白名单里。

    宿主组件类**无条件注入**（1.4.8 lib/plugin-page-theme.ts:120-130），
    且 :133 / :137 写死 padding ⇒ 加类会连**没装主题时**的内边距一起改掉。

    ⚠ 只扫 class 属性内的类名：``var(--maibot-muted)`` 是**颜色令牌**，
      ``.maibot-muted`` 是**类**，同名不同物。全文搜 maibot- 会误判。

    ⚠ 还必须**先剥注释**：说明文字里常写「可以加 class="maibot-page"」，
      直接扫全文会把这句示范当成真的用了该类。实测踩过。
    """
    class_attr = re.compile(r"""class\s*=\s*["'`]([^"'`]*)["'`]""")
    for page in PAGES:
        html = _code(page)
        classes = " ".join(class_attr.findall(html))
        found = set(re.findall(r"\bmaibot-[\w-]+\b", classes))
        if ROUTE_ONE:
            continue          # 路线一：宿主类是刻意使用的，不做白名单限制
        extra = sorted(found - set(ALLOWED_HOST_CLASSES))
        assert not extra, (
            f"{page}.html 出现未授权的宿主类: {extra}；"
            "路线二不应新增控件类，确需使用请加入 ALLOWED_HOST_CLASSES 并说明理由"
        )
        for allowed in ALLOWED_HOST_CLASSES:
            if allowed == "maibot-page":
                continue      # 根容器类可选，不强制
            assert allowed in classes, (
                f"{page}.html 丢了白名单里的既有类 {allowed}（可能是误删）"
            )


def test_no_dead_focus_ring():
    """★ 焦点规则要么真生效，要么别写。

    宿主 ``:focus,:focus-visible{outline:none!important}``。
    层叠**先比 !important 级别**，再比特异性 ⇒ 不带 important 必输，
    特异性再高也救不回来 ⇒ 那条规则**从来没渲染过**，是死代码。

    删死代码屏幕零变化；但**带 important 的那条是真能力**，删了是真功能退化。
    """
    for page in PAGES:
        for sel, body in _rules(_style(page)):
            if "focus" not in sel:
                continue
            outline = re.search(r"outline\s*:\s*([^;]+)", body)
            if not outline or outline.group(1).strip().startswith("none"):
                continue
            assert "!important" in outline.group(1), (
                f"{page}.html 的 {sel[:60]} 焦点规则不带 !important ⇒ 死代码，"
                "要么加 important 并提高特异性，要么删掉"
            )


@pytest.mark.skipif(REAL_FOCUS_RING is None, reason="本插件没有既有真焦点环")
def test_existing_focus_ring_is_preserved():
    """★ 既有真生效的焦点环必须保住（含它自身的 border-radius）。

    做形状适配时最容易顺手删掉它 —— 那是**真功能退化**，
    键盘用户会真的失去焦点提示。焦点框自带的圆角是**焦点框形状**，
    不是装饰圆角，也不该压平。

    ⚠ 必须按**真实规则**查找，不能用 ``REAL_FOCUS_RING in style`` 子串判断：
      注释里的示范文字（``.x :focus-visible { outline: ... !important }``）
      会让子串检查在规则被删后仍然「找到」⇒ 用例静默失效。实测踩过。
    """
    for page in PAGES:
        rules = [(s, b) for s, b in _rules(_style(page)) if REAL_FOCUS_RING in s]
        assert rules, (
            f"{page}.html 丢了既有焦点环规则 {REAL_FOCUS_RING}"
            "（注释里提到它不算，必须是真实规则）"
        )
        for sel, body in rules:
            outline = re.search(r"outline\s*:\s*([^;]+)", body)
            assert outline, f"{page}.html 的 {sel} 丢了 outline 声明"
            assert "!important" in outline.group(1), (
                f"{page}.html 焦点环丢了 !important（会退化成死代码）"
            )
            assert not outline.group(1).strip().startswith("none"), (
                f"{page}.html 焦点环被改成 outline:none"
            )


@pytest.mark.skipif(not SEMANTIC_DOTS, reason="本插件没有语义圆点")
def test_semantic_dots_stay_round():
    """★ 语义圆点两个方向都要钉。

    ① 门控层里不许出现圆点选择器（那是「主题下压平」）；
    ② **原始规则本身**必须仍是 50%。

    只钉 ① 是不够的：有人绕过门控直接改死值，① 抓不到，
    而未装主题时圆点也变方块了。这条是反向验证补出来的。

    ⚠ 圆点分布可能不对称（某些点只在某一页有），所以按页取
      「该页实际存在的圆点」，不硬求每页都齐全。

    ⚠ 判「有没有压平」要看**该规则是否真的声明了 border-radius**，
      不能只看门控行里有没有出现圆点类名 ——
      ``html[data-ef-page='on'] .dot.is-running { animation: ... }``
      是给圆点加动画，完全合法。按行匹配类名会把它误报成压平（实测踩过）。
    """
    seen = set()
    for page in PAGES:
        style = _style(page)
        for sel, body in _rules(style):
            if GATE not in sel:
                continue
            if not any(d in sel for d in SEMANTIC_DOTS):
                continue
            assert not re.search(r"border-radius\s*:", body), (
                f"{page}.html 把语义圆点压平了: {sel} {{{body.strip()[:80]}}}"
            )
        # 「该页有哪些圆点」看**不带门控**的原始规则里有没有它的 border-radius
        present = []
        for dot in SEMANTIC_DOTS:
            bodies = [b for s, b in _rules(style)
                      if dot in s and GATE not in s
                      and re.search(r"border-radius\s*:", b)]
            if not bodies:
                continue
            present.append(dot)
            for body in bodies:
                m = re.search(r"border-radius\s*:\s*([^;]+)", body)
                assert m.group(1).strip() == "50%", (
                    f"{page}.html {dot} 圆角被改成 {m.group(1).strip()}，语义圆点须保持 50%"
                )
        seen.update(present)
    assert seen == set(SEMANTIC_DOTS), (
        f"配置的语义圆点应在各页间合计出现，实际只覆盖 {sorted(seen)}；"
        "选择器可能被改名了"
    )


@pytest.mark.skipif(not HARDCODED_ROUND, reason="本插件没有写死装饰圆角")
def test_hardcoded_round_is_flattened_under_gate():
    """★ 写死装饰圆角必须在门控层里被压平。

    ``999px`` / 写死 px 主题**管不到** —— 令牌变成 0 也不会影响它们，
    方角主题下这些元素仍是圆的，是「吃到颜色吃不到形状」的典型症状。

    两个方向都要钉：
    ① 门控层里**有**该选择器且声明了 ``border-radius: 0``；
    ② 原始规则**仍是写死值**（没被误改成走令牌 —— 那也合法，
       但说明配置区该更新了，应当被 review 而不是静默通过）。

    ⚠ 走 ``var(--maibot-radius)`` 的圆角不要列进 HARDCODED_ROUND：
      它本来就跟随，再写一条门控是多余规则，会让人误以为令牌没生效。
    """
    for page in PAGES:
        style = _style(page)
        rules = list(_rules(style))
        for sel in HARDCODED_ROUND:
            gated = [b for s, b in rules
                     if GATE in s and sel in s
                     and re.search(r"border-radius\s*:\s*0(?:px)?\s*(?:;|$)",
                                   b.strip())]
            assert gated, (
                f"{page}.html 的 {sel} 写死圆角没在门控层里压平；"
                "加一条 " + GATE + f" {sel} {{ border-radius: 0; }}"
            )
            plain = [b for s, b in rules
                     if GATE not in s and sel in s
                     and re.search(r"border-radius\s*:", b)]
            assert plain, f"{page}.html 找不到 {sel} 的原始圆角规则（选择器改名了？）"
            for body in plain:
                value = re.search(r"border-radius\s*:\s*([^;]+)", body).group(1)
                assert "var(" not in value, (
                    f"{page}.html 的 {sel} 已改走令牌（{value.strip()}），"
                    "这是好事，但请把它从 HARDCODED_ROUND 移除并删掉多余的门控规则"
                )


def test_accent_text_uses_paired_foreground():
    """★ 强调色底上的文字必须取宿主配套前景色，不能写死白。

    主题深色下强调色是荧光黄绿，白字对比度只有 1.1~1.8（看不见字）。
    宿主同时下发 primary 与 primary-foreground 就是为了这个配对。

    ⚠ 判定要**追溯变量定义链**，不能只看变量名：
      ``--x-accent: #1baf7a``（写死绿）**不跟随主题**，白字够用，不该报；
      ``--accent: var(--maibot-primary)`` 才真跟随。
    """
    for page in PAGES:
        style = re.sub(r"/\*.*?\*/", "", _style(page), flags=re.S)
        defs = {}
        for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;}]+)", style):
            defs[m.group(1)] = m.group(2).strip()

        def follows(value: str, host: str, depth: int = 0) -> bool:
            if depth > 12:
                return False
            for name in re.findall(r"var\(\s*(--[\w-]+)", value):
                if name == host:
                    return True
                if name in defs and follows(defs[name], host, depth + 1):
                    return True
            return False

        for sel, body in _rules(style):
            bg = re.search(r"background(?:-color)?\s*:\s*([^;]+)", body)
            fg = re.search(r"(?<![-\w])color\s*:\s*([^;]+)", body)
            if not bg or not fg:
                continue
            if not follows(bg.group(1), "--maibot-primary"):
                continue
            # 用了配套前景色 ⇒ 正确
            if follows(fg.group(1), "--maibot-primary-foreground"):
                continue
            assert not re.search(r"#fff\b|#ffffff\b|\bwhite\b", fg.group(1), re.I), (
                f"{page}.html 的 {sel[:60]} 强调色底配写死白字，"
                "装主题后看不清；改用 var(--maibot-primary-foreground)"
            )


def test_dark_mode_reads_host_class():
    """深浅读 html.dark，不读系统偏好（用户手动选择可能与系统不一致）。"""
    for page in PAGES:
        assert "prefers-color-scheme" not in _code(page), (
            f"{page}.html 用了 prefers-color-scheme；宿主已把真实选择同步成 html.dark"
        )


def test_pulse_animation_respects_reduced_motion():
    """无限动画必须包在 prefers-reduced-motion: no-preference 里。

    用户要求减少动效时整块不生效 ⇒ 静止态仍要能表达状态（别只靠动画）。
    """
    for page in PAGES:
        style = re.sub(r"/\*.*?\*/", "", _style(page), flags=re.S)
        if not re.search(r"animation:[^;{}]*infinite", style):
            continue
        assert "prefers-reduced-motion" in style, (
            f"{page}.html 有无限动画但没做 reduced-motion 门控"
        )


def test_probe_uses_capability_not_brand():
    """★ 探测按能力（界面长什么样），不按品牌。

    宿主不传「装了哪个主题」——**装主题时 dashboardStyle 仍是 modern**，
    按品牌判必然漏判。判据 = 圆角令牌归零 + 字体族含宽体拉丁，两条都中。
    主题样式随 context 下发（初始 srcDoc 里没有），必须监听事件；
    字体异步 data: 注入，就绪后要补判一次。
    """
    for page in PAGES:
        html = _html(page)
        if "data-ef-page" not in html:
            pytest.skip(f"{page}.html 未做形状跟随层")
        for key in ("--maibot-radius", "--maibot-font-body", "maibot:context",
                    "data-ef-page", "removeAttribute", "document.fonts.ready"):
            assert key in html, f"{page}.html 探测缺少要素: {key}"
        assert not re.search(
            r"(?:dataset|context)\s*(?:\.|\[\s*['\"])dashboardStyle", _code(page)
        ), f"{page}.html 不得读 dashboardStyle 判主题品牌"


@pytest.mark.skipif(len(PAGES) < 2, reason="单页插件无需跨页比对")
def test_probe_and_gate_identical_across_pages():
    """★ CSP 禁外链 ⇒ 每页内联一份，副本必须**逐字节一致**。

    漏改一页那页就**静默不跟随主题**（不报错、只是变回圆角），极难发现。
    这条断言把「副本同步」变成机器保证。
    有 build 脚本时，改源后必须重跑生成，否则真机加载的还是旧产物。
    """
    def segment(page: str, start: str, end: str | None) -> str:
        text = _html(page)
        head = text.index(start)
        stop = text.index(end, head) if end else text.index("</style>", head)
        return text[head:stop]

    base_probe = segment(PAGES[0], PROBE_START, PROBE_END)
    base_gate = segment(PAGES[0], GATE_START, None)
    for page in PAGES[1:]:
        assert segment(page, PROBE_START, PROBE_END) == base_probe, (
            f"{page}.html 探测代码与 {PAGES[0]}.html 不一致，改判据要各页同步"
        )
        assert segment(page, GATE_START, None) == base_gate, (
            f"{page}.html 门控 CSS 与 {PAGES[0]}.html 不一致"
        )


def test_no_external_resources():
    """沙箱 CSP 是 default-src 'none'：外链与 fetch 一律失败。

    数据只能走 maibot.query / maibot.action；图片只能 data:/blob:，字体只能 data:。
    """
    for page in PAGES:
        code = _code(page)
        scripts = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", code, flags=re.S))
        for pattern, label in ((r"\bfetch\s*\(", "fetch"),
                               (r"\bXMLHttpRequest\b", "XMLHttpRequest"),
                               (r"\bnew\s+WebSocket\b", "WebSocket")):
            assert not re.search(pattern, scripts), (
                f"{page}.html 用了 {label}，沙箱 connect-src 'none' 会拦"
            )
        assert not re.search(r"""(?:src|href)\s*=\s*["'](https?:)?//""", code), (
            f"{page}.html 引用了外链资源，CSP 会拦"
        )
