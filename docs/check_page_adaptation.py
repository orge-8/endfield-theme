#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""插件自定义 WebUI 页面适配自检（零依赖，只用标准库）。

用法：
    python check_page_adaptation.py <插件目录>
    python check_page_adaptation.py <插件目录> --json      # 机器可读
    python check_page_adaptation.py <插件目录> --strict    # 隐患也算失败

退出码：0 = 无现症；1 = 有现症（--strict 下隐患也算）；2 = 用法/目录错误。

--------------------------------------------------------------------------
设计要点（都是实测踩出来的，改这个脚本前先读）
--------------------------------------------------------------------------
1. **必须跨行解析整条规则**。只匹配 `color:#fff` 紧挨 `background` 的窄正则
   会漏掉多行写法 —— 实测漏检过 self-identity 的三处。这里用 re.S 解析
   `选择器{...}` 整块，再逐条拆声明。
2. **必须追溯变量定义，不能只看变量名**。名字里有 `accent` 不代表它跟随主题：
   self-identity 的 `--si-accent` 是写死的 `#1baf7a`，配白字对比度 2.82 合格；
   而 `--accent: var(--maibot-primary)` 才真跟随。只看名字会误报「看不见字」。
3. **区分现症与隐患**。判据是**回退值**：
   - `var(--x, 12px)` 减 4 ⇒ 8px 为正 ⇒ 主题下才可能出问题 ⇒ 隐患；
   - 宿主令牌是**无条件注入**的（从 dashboard 实测采样），所以裸 `var(--maibot-radius)`
     在没装主题时也有值（官方 modern 8px / millennium 0px / future-retro 4px），
     **不是「变量不存在」**。只有减法算出负数才是问题。
4. **类名只扫 class 属性内**。`.maibot-muted` 是类，`var(--maibot-muted)` 是颜色令牌，
   同名不同物。全文搜 `maibot-` 会把令牌误判成类。
5. **注释不算违规**。判「有没有读 dashboardStyle」要匹配真实取值表达式，
   不能因为注释里解释了「为什么不按品牌判」就报违规。
6. **能力探测的副本一致性**。CSP 禁外链 ⇒ 探测代码每页内联，漏改一页那页静默不跟随。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

# 宿主无条件注入的令牌（dashboard lib/plugin-page-theme.ts:95-118 实测采样）
HOST_TOKENS = (
    "background", "surface", "foreground", "muted", "soft", "border",
    "primary", "primary-foreground", "danger", "radius",
    "font-body", "font-display", "font-mono",
)
# 官方三风格卡片圆角实测值（lib/theme/tokens.ts；Card 用 rounded-lg）
OFFICIAL_RADIUS = {"modern": 8.0, "millennium": 0.0, "future-retro": 4.0}
# 宿主组件类：无条件注入且写死 padding，加了会连没装主题时的外观一起改
CONTROL_CLASSES = (
    "button", "card", "input", "select", "badge", "table", "inset", "number", "muted",
)
GATE_ATTR = "data-ef-page"


# --------------------------------------------------------------------- 基础解析

def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def strip_all_comments(html: str) -> str:
    """剥掉 HTML / CSS / JS 三种注释，供「代码里有没有用某写法」类检查使用。

    ★ 必须先剥注释再扫，否则**文档性注释会被当成违规代码**。
      实测误报：样例页注释里写了「不要读 prefers-color-scheme」和
      「装主题时 context.dashboardStyle 仍是 modern」，
      两条解释性文字都被判成现症。教人别踩坑的注释反而被报错，是最坏的一种误报。
    """
    out = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    out = re.sub(r"/\*.*?\*/", "", out, flags=re.S)
    # JS 行注释：避开 http:// 这类冒号斜杠（前面要求不是 ':' 且不是字符串内简判）
    out = re.sub(r"(?<![:\w])//[^\n]*", "", out)
    return out


def rules_of(css: str):
    """产出 (选择器, [(属性, 值), ...])。跨行、多声明、嵌套 @ 块都能处理。"""
    css = strip_comments(css)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel = " ".join(m.group(1).split())
        if not sel or sel.startswith("@"):
            continue
        decls = []
        for part in m.group(2).split(";"):
            if ":" not in part:
                continue
            prop, value = part.split(":", 1)
            decls.append((prop.strip().lower(), " ".join(value.split())))
        yield sel, decls


def styles_of(html: str) -> str:
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.S))


def var_definitions(css: str) -> dict:
    """收集自定义属性定义，用于追溯「这个变量到底跟随不跟随主题」。"""
    defs = {}
    for _, decls in rules_of(css):
        for prop, value in decls:
            if prop.startswith("--"):
                defs[prop] = value
    return defs


def resolve(value: str, defs: dict, depth: int = 0) -> str:
    """把 var() 逐层展开成最终字面量（带环保护）。"""
    if depth > 12:
        return value
    def sub(m):
        name = m.group(1).strip()
        fallback = (m.group(2) or "").strip()
        if name in defs:
            return resolve(defs[name], defs, depth + 1)
        return fallback
    # 只展开最内层 var()，避免嵌套括号配对问题
    pattern = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*))?\)")
    prev = None
    out = value
    while prev != out and depth <= 12:
        prev = out
        out = pattern.sub(sub, out)
        depth += 1
    return out


def hex_colors(text: str) -> list:
    return re.findall(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", text)


def to_rgb(color: str):
    color = color.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3})", color)
    if m:
        return tuple(int(c * 2, 16) for c in m.group(1))
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", color)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)", color)
    if m:
        return tuple(int(float(m.group(i))) for i in (1, 2, 3))
    named = {"white": (255, 255, 255), "black": (0, 0, 0)}
    return named.get(color.lower())


def luminance(rgb) -> float:
    def chan(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# 主题四档强调色实测值（浅底上的荧光色，配白字对比度极低）
THEME_ACCENTS = {
    "yellow": "#d8f000", "lime": "#a8e000", "ice": "#7fe8e0", "amber": "#ffb300",
}


# --------------------------------------------------------------------- 检查项

class Finding:
    def __init__(self, level, code, page, message, hint=""):
        self.level = level      # "现症" | "隐患" | "提示"
        self.code = code
        self.page = page
        self.message = message
        self.hint = hint

    def as_dict(self):
        return {"level": self.level, "code": self.code, "page": self.page,
                "message": self.message, "hint": self.hint}


def check_negative_radius(page, css, findings):
    """派生圆角必须钳住。区分现症/隐患看回退值与官方取值。"""
    defs = var_definitions(css)
    for sel, decls in rules_of(css):
        for prop, value in decls:
            if "radius" not in prop:
                continue
            # ⚠ 不能用 `calc\([^)]*-` ：`[^)]*` 遇到 var(...) 的**内层右括号**就停，
            #   永远匹配不到后面的减号（回测时 5 个插件的负圆角一处都没抓到）。
            #   calc() 里必然嵌套 var()，所以直接找「减去一个数」的模式。
            if not re.search(r"-\s*\d+(?:\.\d+)?px", value):
                continue
            if "calc(" not in value:
                continue
            if re.search(r"max\(\s*0", value):
                continue
            # 找出被减的令牌与减数（回退值里可能含逗号与空格）
            m = re.search(
                r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*?))?\s*\)\s*-\s*(\d+(?:\.\d+)?)px",
                value)
            if not m:
                findings.append(Finding(
                    "隐患", "RADIUS-NEG", page,
                    f"{sel} 的 {prop} 用了减法但未钳下界: {value}",
                    "改成 max(0px, calc(...))"))
                continue
            token, fallback, minus = m.group(1), (m.group(2) or "").strip(), float(m.group(3))
            # 追溯该令牌最终指向哪个宿主令牌
            chain = defs.get(token, "")
            base = resolve(f"var({token})", defs)
            follows_host = "--maibot-radius" in chain or token == "--maibot-radius"
            # 没装主题时的值：回退值优先，否则用官方 modern 实测值
            fb_num = re.match(r"([\d.]+)px", fallback or base)
            unthemed = float(fb_num.group(1)) if fb_num else (
                OFFICIAL_RADIUS["modern"] if follows_host else None)
            worst = None
            if follows_host:
                worst = min(OFFICIAL_RADIUS.values()) - minus
            if unthemed is not None and unthemed - minus < 0:
                level = "现症"
                detail = f"没装主题时也会算出 {unthemed - minus:g}px"
            elif worst is not None and worst < 0:
                level = "隐患"
                detail = (f"没装主题时是 {unthemed - minus:g}px（正常），"
                          f"但官方千禧风圆角为 0 ⇒ {worst:g}px 非法")
            else:
                level = "隐患"
                detail = "令牌被调小时可能算出负值"
            findings.append(Finding(
                level, "RADIUS-NEG", page,
                f"{sel} 的 {prop}: {value} —— {detail}",
                "改成 max(0px, calc(...))；border-radius 不继承，"
                "非法值被丢弃后取初始值 0，会静默丢掉层级差"))


def follows_host_token(value: str, defs: dict, host: str) -> bool:
    """判断一个值是否**最终指向某个宿主令牌**（而不是只用了它的回退值）。

    ★ 这是上一版脚本误报的根源，也是本版最容易写错的地方：
      · `--si-accent: #1baf7a`（写死绿）⇒ **不跟随** ⇒ 白字对比度 2.82 合格，不该报；
      · `--accent: var(--maibot-primary, #4f6f52)` ⇒ **跟随** ⇒ 装主题后走荧光色，
        白字必挂。注意此时**不能**展开到回退值 `#4f6f52` 去算对比度 ——
        回退值只在宿主令牌为空时才用，而宿主令牌是无条件注入的，永远有值。
    所以要沿定义链找宿主令牌名，而不是把 var() 展开成字面量。
    """
    seen = set()
    stack = [value]
    while stack:
        cur = stack.pop()
        for name in re.findall(r"var\(\s*(--[\w-]+)", cur):
            if name == host:
                return True
            if name in seen:
                continue
            seen.add(name)
            if name in defs:
                stack.append(defs[name])
        if host in re.sub(r",[^)]*", "", cur):
            # 直接写了宿主令牌名（无 var 包裹的异常情况）
            if re.search(re.escape(host) + r"\b", cur):
                return True
    return False


def check_white_on_accent(page, css, findings):
    """荧光强调色配白字 ⇒ 看不见字。必须追溯变量定义链，不能只看名字或回退值。"""
    defs = var_definitions(css)
    for sel, decls in rules_of(css):
        bg = fg = None
        for prop, value in decls:
            if prop in ("background", "background-color"):
                bg = value
            elif prop == "color":
                fg = value
        if not bg or not fg:
            continue
        # ★ 文字色若取自宿主的配套前景色，装主题后会自动跟着变（荧光底配墨字），
        #   这是**正确写法**，不能报。上一版把它展开成回退值 #ffffff 去算对比度，
        #   于是把 self-identity 的 .si-btn-primary 误报成「看不见字」。
        #   宿主同时下发 primary 与 primary-foreground 就是为了这个配对。
        if follows_host_token(fg, defs, "--maibot-primary-foreground"):
            continue
        fg_rgb = to_rgb(resolve(fg, defs))
        if fg_rgb != (255, 255, 255):
            continue
        # ① 背景最终指向宿主强调色 ⇒ 装主题后是荧光色，白字必挂
        if follows_host_token(bg, defs, "--maibot-primary"):
            worst = []
            for name, hexv in THEME_ACCENTS.items():
                ratio = contrast(to_rgb(hexv), fg_rgb)
                if ratio < 3.0:
                    worst.append(f"{name} {ratio:.2f}")
            if worst:
                findings.append(Finding(
                    "现症", "CONTRAST", page,
                    f"{sel} 白字配主题强调色（背景追溯到 --maibot-primary），"
                    f"装主题后对比度不足: {', '.join(worst)}",
                    "文字改用 var(--maibot-primary-foreground)，"
                    "或按主题给墨色字（实测可达 10 以上）"))
            continue
        # ② 背景是写死色（不跟随任何宿主令牌）⇒ 主题管不到它，
        #    对比度不足是**既有设计问题，不是主题适配缺陷** ⇒ 只给提示。
        #    例：self-identity 的 --si-accent: #1baf7a 配白字实测 2.82，
        #    低于 WCAG AA 对大字号/图形的 3.0，但它不随主题变，
        #    报「现症」会把人误导成「装主题才坏」。
        resolved_bg = resolve(bg, defs)
        bg_rgb = to_rgb(resolved_bg)
        if bg_rgb is None:
            continue
        ratio = contrast(bg_rgb, fg_rgb)
        if ratio >= 3.0:
            continue
        findings.append(Finding(
            "提示", "CONTRAST-STATIC", page,
            f"{sel} 白字配写死底色 {resolved_bg}，对比度 {ratio:.2f}（低于 3.0）",
            "该底色不跟随主题，属既有配色问题而非适配缺陷；"
            "想改就把底色改走令牌，或文字改深色"))


def gated_selectors(css: str) -> set:
    """收集**已在门控层里被压平**的选择器。

    ★ 写死圆角只要门控层已经压平，就是**正确做法**，不该再报隐患。
      实测误报：路线二样例的 .demo-badge / .demo-bar-track / .demo-bar-fill
      写死 999px 但门控层已 border-radius:0，脚本仍报隐患 ⇒ 误导使用者去改
      本来就对的代码。
    """
    out = set()
    for sel, decls in rules_of(css):
        if GATE_ATTR not in sel:
            continue
        if not any(p == "border-radius" and v in ("0", "0px") for p, v in decls):
            continue
        # 去掉门控前缀，按逗号拆出每个被压平的选择器
        body = re.sub(r"html\[" + GATE_ATTR + r"[^\]]*\]\s*", "", sel)
        for part in body.split(","):
            part = " ".join(part.split())
            if part:
                out.add(part)
    return out


def check_hardcoded_radius(page, css, findings):
    """写死装饰圆角主题管不到；真圆点与已门控压平的例外。"""
    gated = gated_selectors(css)
    for sel, decls in rules_of(css):
        if GATE_ATTR in sel:
            continue                      # 门控层自身不检
        for prop, value in decls:
            if prop != "border-radius":
                continue
            if "var(" in value or "max(" in value or "calc(" in value:
                continue
            if value in ("0", "0px", "none", "inherit", "initial", "unset"):
                continue
            # ★ 焦点框自身的圆角不是装饰圆角，不该压平也不该报
            if "focus" in sel:
                findings.append(Finding(
                    "提示", "RADIUS-FOCUS", page,
                    f"{sel} 的 border-radius {value} 是焦点框自身形状",
                    "不是装饰圆角，形状适配时应保留，不要压平"))
                continue
            if value == "50%":
                findings.append(Finding(
                    "提示", "RADIUS-DOT", page,
                    f"{sel} 用 50% —— 若它是状态灯/进度点则合理，若是装饰块需门控压平",
                    "判断标准是「它是不是一个点」，不是「它圆不圆」"))
                continue
            # ★ 已被门控层压平 ⇒ 正确做法，不报
            if any(sel == g or sel in g or g in sel for g in gated):
                continue
            findings.append(Finding(
                "隐患", "RADIUS-HARDCODED", page,
                f"{sel} 的 border-radius 写死 {value}，主题管不到且门控层未压平",
                "改走 var(--maibot-radius)，或在门控层里压平"))


def check_ungated_square(page, css, findings):
    """直角声明必须挂门控，否则没装主题时外观也变了。"""
    plain = strip_comments(css)
    for line in plain.splitlines():
        if not re.search(r"border-radius:\s*0\s*[;}]", line):
            continue
        if GATE_ATTR in line:
            continue
        findings.append(Finding(
            "现症", "GATE-MISSING", page,
            f"直角声明没挂门控: {line.strip()[:110]}",
            f"加 html[{GATE_ATTR}='on'] 前缀，只在探测命中时生效"))


def check_focus_ring(page, css, findings):
    """不带 !important 的焦点规则是死代码；带的要提醒别误删。"""
    for sel, decls in rules_of(css):
        if "focus" not in sel:
            continue
        for prop, value in decls:
            if prop != "outline" or value.startswith("none"):
                continue
            if "!important" in value:
                findings.append(Finding(
                    "提示", "FOCUS-REAL", page,
                    f"{sel} 的焦点环带 !important ⇒ 真正在渲染，是既有键盘能力",
                    "做形状适配时不要顺手删它（删了是真功能退化）"))
            else:
                findings.append(Finding(
                    "现症", "FOCUS-DEAD", page,
                    f"{sel} 的 outline 不带 !important ⇒ 输给宿主 "
                    ":focus{outline:none!important}，从来没渲染过",
                    "删掉这条死代码；键盘可用性要靠自己的状态驱动"))


def check_host_classes(page, html, findings):
    """只扫 class 属性内的类名 —— var(--maibot-muted) 是令牌不是类。"""
    attrs = re.findall(r"""class\s*=\s*["']([^"']*)["']""", html)
    # JS 模板字符串里的 class 也要扫（渲染后才出现）
    attrs += re.findall(r"""className\s*=\s*["'`]([^"'`]*)["'`]""", html)
    seen = set()
    for attr in attrs:
        for name in re.findall(r"\bmaibot-[\w-]+\b", attr):
            seen.add(name)
    controls = sorted(n for n in seen
                      if n[len("maibot-"):] in CONTROL_CLASSES)
    if controls:
        findings.append(Finding(
            "提示", "HOST-CLASS", page,
            f"使用了宿主控件类: {', '.join(controls)}",
            "这些类无条件注入且写死 padding（plugin-page-theme.ts:133/137），"
            "加了会连没装主题时的内边距一起改。走「只用令牌」路线就该去掉"))
    if "maibot-page" not in seen:
        findings.append(Finding(
            "提示", "HOST-PAGE", page,
            "根容器没有 maibot-page 类",
            "路线一需要它来继承底色/文字色/字体；路线二可以不要"))


def check_probe(page, html, findings):
    """探测必须按能力判、监听 context、等字体就绪。"""
    if GATE_ATTR not in html:
        return
    for key, why in (
        ("--maibot-radius", "圆角判据"),
        ("--maibot-font-body", "字体判据"),
        ("maibot:context", "主题样式随 context 下发，初始 srcDoc 里没有"),
        ("removeAttribute", "不命中时要摘掉开关，否则切风格后残留"),
        ("document.fonts.ready", "字体异步 data: 注入，首帧可能还没解析出来"),
    ):
        if key not in html:
            findings.append(Finding(
                "现症", "PROBE-INCOMPLETE", page,
                f"探测缺少要素 {key}（{why}）", ""))
    # 只匹配真实取值表达式；先剥注释，避免解释性文字被判违规
    code = strip_all_comments(html)
    if re.search(r"(?:dataset|context)\s*(?:\.|\[\s*['\"])dashboardStyle", code):
        findings.append(Finding(
            "现症", "PROBE-BRAND", page,
            "探测读了 dashboardStyle 判品牌",
            "装主题时该字段仍是 modern，按品牌判必然漏判；要按能力判"))


def check_csp(page, html, findings):
    """沙箱 CSP 禁外链：fetch / XHR / 外链图片必然违规。"""
    scripts = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.S))
    scripts = re.sub(r"//[^\n]*", "", scripts)
    for pattern, label in (
        (r"\bfetch\s*\(", "fetch"),
        (r"\bXMLHttpRequest\b", "XMLHttpRequest"),
        (r"\bnew\s+WebSocket\b", "WebSocket"),
    ):
        if re.search(pattern, scripts):
            findings.append(Finding(
                "现症", "CSP", page, f"脚本里用了 {label}",
                "沙箱 connect-src 'none'，一律失败；数据只能走 maibot.query/action"))
    for m in re.finditer(r"""(?:src|href)\s*=\s*["'](https?:)?//""", html):
        findings.append(Finding(
            "现症", "CSP", page, "页面引用了外链资源",
            "沙箱 default-src 'none'；图片只能 data:/blob:，字体只能 data:"))
        break


def check_dark_mode(page, html, findings):
    """深浅要读 html.dark，不要读系统偏好。先剥注释再扫。"""
    code = strip_all_comments(html)
    if "prefers-color-scheme" in code:
        findings.append(Finding(
            "现症", "DARK", page, "用了 prefers-color-scheme 判深浅",
            "用户在 dashboard 手动选的深浅可能与系统不一致；改用 html.dark"))


def check_motion(page, css, findings):
    """无限动画要尊重系统的「减少动态效果」开关。"""
    plain = strip_comments(css)
    infinite = re.findall(r"animation:[^;{}]*infinite", plain)
    if not infinite:
        return
    if "prefers-reduced-motion" in plain:
        return
    findings.append(Finding(
        "隐患", "MOTION", page,
        f"有 {len(infinite)} 处无限动画但没做 prefers-reduced-motion 门控",
        "把 animation 包进 @media (prefers-reduced-motion: no-preference)"))


def check_fragment(page, html, findings):
    """custom 页产物应是 body 片段，宿主自己补 doctype/html/head/body。

    ⚠ 级别定为**隐患**不是现症：宿主 ``customPageDocument``
    （lib/plugin-custom-page.ts:179-184）无条件把 entry 内容塞进 ``<body>``，
    完整文档会形成嵌套结构。但浏览器 HTML 解析器会容错剥掉内层
    doctype/html/head/body 标签，把内容提升上来 —— 所以**真机往往看起来正常**
    （char-recog 七页都是完整文档，长期真机可用）。
    这是「依赖解析器容错」而非合规：内层 <head> 里的 <meta>/<title> 会被丢弃，
    宿主 CSP 与 SDK 注入位置也不受你控制。故报隐患、给出事实，不谎报现症。
    """
    lowered = html.lower()
    hits = []
    if "<!doctype" in lowered:
        hits.append("doctype")
    for tag in ("html", "head", "body"):
        if re.search(rf"<{tag}[\s>]", lowered):
            hits.append(f"<{tag}>")
    if hits:
        findings.append(Finding(
            "隐患", "FRAGMENT", page,
            f"产物是完整文档而非 body 片段（含 {', '.join(hits)}）",
            "宿主 customPageDocument 会自己补这些标签，形成嵌套结构。"
            "浏览器容错会剥掉内层标签，所以真机通常仍能显示，"
            "但内层 head 里的 meta/title 会被丢弃。建议只留 body 内容"))


# --------------------------------------------------------------------- 主流程

CHECKS_CSS = (
    check_negative_radius, check_white_on_accent, check_hardcoded_radius,
    check_ungated_square, check_focus_ring, check_motion,
)


def probe_segment(html: str):
    """抽出探测段用于跨页一致性比对（取开关属性相关的函数体）。"""
    m = re.search(r"function\s+\w*[Dd]etect\w*\s*\([^)]*\)\s*\{", html)
    if not m:
        return None
    start = m.start()
    # 往前带上判据常量，往后到字体就绪回调
    head = html.rfind("/*", 0, start)
    if head != -1 and start - head < 900:
        start = head
    tail = html.find("fonts.ready", start)
    end = html.find("\n", tail) if tail != -1 else start + 1200
    return html[start:end]


def scan(plugin_dir: pathlib.Path):
    findings = []
    declaration = plugin_dir / "webui.json"
    pages = []
    if declaration.is_file():
        try:
            data = json.loads(declaration.read_text(encoding="utf-8"))
            for page in data.get("pages", []):
                if page.get("mode") == "custom" and page.get("entry"):
                    pages.append(plugin_dir / page["entry"])
        except Exception as exc:
            findings.append(Finding("现症", "DECL", "webui.json",
                                    f"声明解析失败: {exc}", ""))
    if not pages:
        pages = sorted((plugin_dir / "webui").glob("*.html")) if (
            plugin_dir / "webui").is_dir() else []
    if not pages:
        return findings, pages, "没有自定义页面 —— 配置页由宿主渲染，主题已自动接管，无需适配"

    segments = {}
    for path in pages:
        if not path.is_file():
            findings.append(Finding("现症", "ENTRY", path.name,
                                    "entry 指向的文件不存在", ""))
            continue
        html = path.read_text(encoding="utf-8")
        css = styles_of(html)
        for check in CHECKS_CSS:
            check(path.name, css, findings)
        check_host_classes(path.name, html, findings)
        check_probe(path.name, html, findings)
        check_csp(path.name, html, findings)
        check_dark_mode(path.name, html, findings)
        check_fragment(path.name, html, findings)
        seg = probe_segment(html)
        if seg:
            segments[path.name] = seg

    if len(segments) > 1:
        base_name = next(iter(segments))
        base = segments[base_name]
        for name, seg in segments.items():
            if seg != base:
                findings.append(Finding(
                    "现症", "PROBE-DRIFT", name,
                    f"探测代码与 {base_name} 不一致",
                    "CSP 禁外链 ⇒ 每页内联一份；漏改一页那页静默不跟随主题。"
                    "若有 build 脚本，改源后重跑生成"))

    # 生成源不在 entry 列表里（如 char-recog 的 index.html）：它不被宿主加载，
    # 但改它不重跑 build 就会让产物与源漂移。这里额外比对一次。
    webui = plugin_dir / "webui"
    if webui.is_dir() and (webui / "build.py").is_file():
        declared = {p.resolve() for p in pages}
        for src in sorted(webui.glob("*.html")):
            if src.resolve() in declared:
                continue
            seg = probe_segment(src.read_text(encoding="utf-8"))
            if seg and segments and seg not in segments.values():
                findings.append(Finding(
                    "现症", "BUILD-STALE", src.name,
                    f"生成源 {src.name} 的探测代码与已生成产物不一致",
                    f"改源后必须重跑 webui/build.py，否则真机加载的还是旧产物"))
    return findings, pages, ""


def selftest():
    """内置自测：用合成样例验证「该抓的抓到、不该报的不报」。

    不依赖任何外部插件目录，任何人都能跑：
        python check_page_adaptation.py --selftest
    每条都对应一个真实踩过的坑，改这个脚本后必须先跑它。
    """
    cases = []

    def collect(css="", html=None):
        found = []
        if html is None:
            html = f"<style>{css}</style>"
        styles = styles_of(html)
        for check in CHECKS_CSS:
            check("t", styles, found)
        check_host_classes("t", html, found)
        check_probe("t", html, found)
        check_csp("t", html, found)
        check_dark_mode("t", html, found)
        check_fragment("t", html, found)
        return found

    def expect(name, found, code, present, level=None):
        hit = any(f.code == code and (level is None or f.level == level) for f in found)
        ok = hit == present
        cases.append((name, ok))
        print(f"{'OK  ' if ok else 'FAIL'} {name}")

    # 1 负圆角：calc 里嵌套 var，正则不能用 [^)]*
    expect("负圆角（带回退值）被抓出",
           collect(".a{border-radius:calc(var(--r, 12px) - 4px)}"),
           "RADIUS-NEG", True)
    expect("负圆角（裸宿主令牌）判为隐患",
           collect(".a{border-radius:calc(var(--maibot-radius) - 3px)}"),
           "RADIUS-NEG", True, "隐患")
    expect("已钳住的 max() 不报",
           collect(".a{border-radius:max(0px,calc(var(--maibot-radius) - 3px))}"),
           "RADIUS-NEG", False)
    # 2 ★ 写死绿底白字：不跟随主题 ⇒ 绝不能报成「现症·装主题才坏」
    #   （#1baf7a 配白字实测 2.82，低于 3.0，但那是既有配色问题，只给提示）
    expect("★ 写死绿底白字不报现症",
           collect(":root{--si-accent:#1baf7a}"
                   ".a{background:var(--si-accent);color:#fff}"),
           "CONTRAST", False)
    expect("写死底色对比度不足只给提示",
           collect(":root{--si-accent:#1baf7a}"
                   ".a{background:var(--si-accent);color:#fff}"),
           "CONTRAST-STATIC", True, "提示")
    expect("写死底色对比度达标不报",
           collect(":root{--ok:#199e70}"
                   ".a{background:var(--ok);color:#fff}"),
           "CONTRAST-STATIC", False)
    # 3 ★ 取宿主配套前景色 ⇒ 正确写法，不许报
    expect("★ 用 primary-foreground 不误报",
           collect(":root{--p:var(--maibot-primary,#2a78d6);"
                   "--pf:var(--maibot-primary-foreground,#ffffff)}"
                   ".a{background:var(--p);color:var(--pf)}"),
           "CONTRAST", False)
    # 4 真 bug：白字直接配宿主强调色 ⇒ 必须报
    expect("白字配宿主强调色被抓出",
           collect(":root{--accent:var(--maibot-primary,#4f6f52)}"
                   ".a{background:var(--accent);color:#fff}"),
           "CONTRAST", True, "现症")
    # 5 焦点环：不带 important 是死代码，带的是真能力
    expect("死焦点环被抓出",
           collect(".a:focus-visible{outline:2px solid red}"),
           "FOCUS-DEAD", True, "现症")
    expect("真焦点环识别为提示",
           collect(".root :focus-visible{outline:2px solid red !important}"),
           "FOCUS-REAL", True, "提示")
    # 6 门控
    expect("无门控直角被抓出",
           collect(".a{border-radius:0}"), "GATE-MISSING", True, "现症")
    expect("带门控直角不报",
           collect("html[data-ef-page='on'] .a{border-radius:0}"),
           "GATE-MISSING", False)
    # 7 ★ 令牌名 ≠ 类名
    expect("★ var(--maibot-muted) 不算控件类",
           collect(".a{color:var(--maibot-muted)}"), "HOST-CLASS", False)
    expect("class 里的控件类被识别",
           collect(html='<style>.a{color:red}</style>'
                        '<button class="maibot-button">x</button>'),
           "HOST-CLASS", True)
    # 8 ★ 注释里提到 dashboardStyle 不算违规
    expect("★ 注释里的 dashboardStyle 不报",
           collect(html="<style>html[data-ef-page='on'] .a{border-radius:0}</style>"
                        "<script>// 装主题时 dashboardStyle 仍是 modern，故不按品牌判\n"
                        "var a=1;</script>"),
           "PROBE-BRAND", False)
    expect("真读 dashboardStyle 被抓出",
           collect(html="<style>html[data-ef-page='on'] .a{border-radius:0}</style>"
                        "<script>var s=window.maibot.context.dataset.dashboardStyle;"
                        "</script>"),
           "PROBE-BRAND", True, "现症")
    # 9 跨行写法（窄正则会漏）
    expect("跨行 background/color 被抓出",
           collect(":root{--accent:var(--maibot-primary,#4f6f52)}\n"
                   ".a{\n  background: var(--accent);\n  color: #fff;\n}"),
           "CONTRAST", True)
    # 10 CSP / 深浅 / 动效
    expect("fetch 被抓出",
           collect(html="<style>.a{color:red}</style><script>fetch('/x')</script>"),
           "CSP", True, "现症")
    expect("prefers-color-scheme 被抓出",
           collect("@media (prefers-color-scheme: dark){.a{color:#fff}}"),
           "DARK", True, "现症")
    expect("无限动画无门控被抓出",
           collect(".a{animation:pulse 1s infinite}"), "MOTION", True)
    expect("动画已门控不报",
           collect("@media (prefers-reduced-motion: no-preference)"
                   "{.a{animation:pulse 1s infinite}}"),
           "MOTION", False)
    # 11 真圆点只给提示，不算缺陷
    expect("50% 只给提示",
           collect(".dot{border-radius:50%}"), "RADIUS-DOT", True, "提示")
    # 12 ★ 已被门控压平的写死圆角是正确做法，不该报隐患
    expect("★ 门控已压平的写死圆角不报",
           collect(".badge{border-radius:999px}\n"
                   "html[data-ef-page='on'] .badge{border-radius:0}"),
           "RADIUS-HARDCODED", False)
    expect("门控未压平的写死圆角仍报",
           collect(".badge{border-radius:999px}"),
           "RADIUS-HARDCODED", True, "隐患")
    # 13 ★ 焦点框自身圆角不是装饰圆角
    expect("★ 焦点框圆角只给提示",
           collect(".root :focus-visible{outline:2px solid red !important;"
                   "border-radius:6px}"),
           "RADIUS-FOCUS", True, "提示")
    expect("★ 焦点框圆角不报装饰隐患",
           collect(".root :focus-visible{border-radius:6px}"),
           "RADIUS-HARDCODED", False)
    # 14 ★ 解释性注释不得被判成违规代码（三种注释都要剥）
    expect("★ HTML 注释里的 prefers-color-scheme 不报",
           collect(html="<style>.a{color:red}</style>"
                        "<!-- 不要读 prefers-color-scheme，要用 html.dark -->"),
           "DARK", False)
    expect("★ CSS 注释里的 prefers-color-scheme 不报",
           collect("/* 别用 prefers-color-scheme */\n.a{color:red}"),
           "DARK", False)
    expect("★ JS 注释里的 dashboardStyle 不报",
           collect(html="<style>html[data-ef-page='on'] .a{border-radius:0}</style>"
                        "<script>// 装主题时 context.dashboardStyle 仍是 modern\n"
                        "var a=1;</script>"),
           "PROBE-BRAND", False)
    expect("真用 prefers-color-scheme 仍报",
           collect("@media (prefers-color-scheme: dark){.a{color:#fff}}"),
           "DARK", True, "现症")

    bad = [c for c in cases if not c[1]]
    print(f"\n{len(cases)-len(bad)}/{len(cases)} 项通过")
    return 1 if bad else 0


def main():
    parser = argparse.ArgumentParser(
        description="插件自定义 WebUI 页面适配自检（零依赖）")
    parser.add_argument("plugin_dir", nargs="?", help="插件目录（含 _manifest.json）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--strict", action="store_true", help="隐患也算失败")
    parser.add_argument("--selftest", action="store_true",
                        help="跑内置自测（合成样例，不依赖外部插件）")
    args = parser.parse_args()

    if args.selftest:
        return selftest()
    if not args.plugin_dir:
        parser.error("需要 plugin_dir，或用 --selftest")

    root = pathlib.Path(args.plugin_dir).resolve()
    if not root.is_dir():
        print(f"目录不存在: {root}", file=sys.stderr)
        return 2

    findings, pages, note = scan(root)
    counts = {"现症": 0, "隐患": 0, "提示": 0}
    for f in findings:
        counts[f.level] += 1

    if args.json:
        print(json.dumps({
            "plugin": str(root), "pages": [p.name for p in pages],
            "counts": counts, "note": note,
            "findings": [f.as_dict() for f in findings],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"自检目标: {root}")
        print(f"扫描页面: {', '.join(p.name for p in pages) or '（无）'}")
        if note:
            print(f"\n{note}")
        print(f"\n现症 {counts['现症']}  隐患 {counts['隐患']}  提示 {counts['提示']}")
        order = {"现症": 0, "隐患": 1, "提示": 2}
        for f in sorted(findings, key=lambda x: (order[x.level], x.page, x.code)):
            print(f"\n[{f.level}] {f.code}  {f.page}")
            print(f"  {f.message}")
            if f.hint:
                print(f"  → {f.hint}")
        if not findings:
            print("\n未发现问题。")
        print("\n注：本脚本是静态扫描，证明不了交互行为。"
              "涉及自定义控件时请另做真实浏览器验收"
              "（真实 iframe + 沙箱 + CSP），静态全绿不等于点了能用。")

    if counts["现症"]:
        return 1
    if args.strict and counts["隐患"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
