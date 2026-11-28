"""官方风格让位层：把主题 CSS 包进「现代风格专属」选择器。

dashboard 的界面风格写在 html[data-dashboard-style]（theme-provider.tsx:103，
取值 modern / future-retro / millennium）。用户选千禧/未来复古时，
本主题整体让位——所有规则失效，界面 100% 官方原样；切回现代即时恢复，
无需重启（纯 CSS 选择器门控，不摘注入）。

实现：逐条规则给选择器加前缀 html:not([data-dashboard-style='millennium'])
:not([data-dashboard-style='future-retro'])。
- html / html.dark / :root 开头的选择器：把门控拼在 html 复合选择器上
  （html.dark → html.dark:not(...):not(...)），保持原有深浅语义；
- 其他选择器：前置门控 + 空格（后代关系）；
- @media / @supports 等条件块：递归处理内部规则，条件本身不动；
- @keyframes：整体跳过（关键帧只在被引用时生效，引用它的规则已被门控）；
- @font-face：整体跳过（字体声明无副作用，字体文件仍随主题分发）。

preamble（变量覆盖）同样逐条门控：html{...} → html:not(...):not(...){...}，
html.dark{...} → html.dark:not(...):not(...){...}。让位时行内 token 不再被压，
官方管线写什么就是什么。
"""

from __future__ import annotations

import re

GATE = ":not([data-dashboard-style='millennium']):not([data-dashboard-style='future-retro'])"

# 条件 at-rule：内部是规则块，递归门控
_CONDITIONAL = re.compile(r"^@(media|supports|container|layer)\b", re.I)
# 整体跳过的 at-rule（声明块，不含选择器）
_SKIP = re.compile(r"^@(keyframes|-webkit-keyframes|font-face|property|charset|import)\b", re.I)
# 规则头部的注释（含空白）。注释紧挨 @media 时不能把整段当选择器，
# 否则会拼出「html:not(...) @media{...}」这种非法 CSS，整块被浏览器丢弃。
_LEADING_COMMENT = re.compile(r"^(?:\s*/\*.*?\*/\s*)+", re.S)


def _gate_selector(sel: str) -> str:
    """给单个选择器加门控。html/:root 开头拼在根复合选择器上，其余前置。"""
    sel = sel.strip()
    if not sel:
        return sel
    m = re.match(r"^(html|:root)((?:\.[\w-]+|\[[^\]]*\]|:[\w-]+(?:\([^)]*\))?)*)", sel)
    if m:
        root, tail = m.group(1), m.group(2)
        rest = sel[m.end():]
        return f"{root}{tail}{GATE}{rest}"
    return f"html{GATE} {sel}"


def _gate_selector_list(sel_list: str) -> str:
    """逗号分隔的选择器列表逐条门控（不拆括号内的逗号——选择器里不会有）。"""
    return ",\n".join(_gate_selector(s) for s in sel_list.split(","))


def gate_css(css: str) -> str:
    """把整份 CSS 的每条规则门控到「非千禧/非未来复古」。

    解析器只处理本主题 CSS 的实际结构：规则块、条件 at-rule 嵌套、
    keyframes/font-face 跳过。不追求通用 CSS 解析。
    """
    out: list[str] = []
    i, n = 0, len(css)
    while i < n:
        # 注释原样保留
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.append(css[i:end])
            i = end
            continue
        # 找到下一个 '{' 之前的头部（选择器或 at-rule 前奏）
        brace = css.find("{", i)
        if brace < 0:
            out.append(css[i:])
            break
        head = css[i:brace]
        # 判断 at-rule 时先剥掉前导注释，输出仍保留原注释
        head_code = _LEADING_COMMENT.sub("", head).strip()
        # 匹配块结束（含嵌套）
        depth, j = 1, brace + 1
        while j < n and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        body = css[brace + 1:j - 1]
        if _SKIP.match(head_code):
            out.append(head + "{" + body + "}")
        elif _CONDITIONAL.match(head_code):
            out.append(head + "{" + gate_css(body) + "}")
        elif head_code.startswith("@"):
            # 其他 at-rule（如 @page）：原样保留
            out.append(head + "{" + body + "}")
        else:
            # 普通规则：头部可能含前置注释/空白，只门控最后一段选择器
            m = re.search(r"([^{}]*)$", head)
            sel_part = m.group(1) if m else head
            prefix = head[:len(head) - len(sel_part)]
            # 选择器段里可能混着行尾注释，按最后一个注释结束切
            cm = None
            for cm in re.finditer(r"/\*.*?\*/", sel_part, re.S):
                pass
            if cm:
                sel = sel_part[cm.end():]
                out.append(prefix + sel_part[:cm.end()] + _gate_selector_list(sel) + "{" + body + "}")
            else:
                out.append(prefix + _gate_selector_list(sel_part) + "{" + body + "}")
        i = j
    return "".join(out)


def gate_preamble(preamble: str) -> str:
    """preamble 只有 html{...} 与 html.dark{...} 两块，逐块门控。"""
    return gate_css(preamble)