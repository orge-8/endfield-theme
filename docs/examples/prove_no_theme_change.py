# -*- coding: utf-8 -*-
"""prove_no_theme_change.py — 机器证明「没装主题时外观不变」。

★ 自包含、零第三方依赖（只用标准库），系统 Python 直接跑。

--------------------------------------------------------------------------
它证明什么
--------------------------------------------------------------------------
走路线二（只用令牌 + 门控 CSS）时，你的硬约束通常是：
**没装主题的用户，页面要与改造前逐像素一致。**

肉眼看不出来，靠「我每条都加了门控」的自觉也不可靠。做法是：

  1. 取改造前 / 改造后两个 HTML；
  2. 各自抽出 <style> 里的全部规则，展开成 (选择器, 属性, 值) 三元组；
  3. **剥掉所有带门控的规则**（没装主题时它们不生效）；
  4. 求集合差：净新增必须 0、净删除必须 0。

唯一允许的差异是 ``max(0px, calc(...))`` 包装 —— 在正常令牌值下计算等价，
它修的是「令牌归零时算出负值」的隐患，不改变正常观感。

--------------------------------------------------------------------------
用法
--------------------------------------------------------------------------
    python prove_no_theme_change.py BEFORE.html AFTER.html
    python prove_no_theme_change.py BEFORE.html AFTER.html --gate data-ef-page
    python prove_no_theme_change.py BEFORE.html AFTER.html --json
    python prove_no_theme_change.py --selftest

退出码：0 证明成立 / 1 有净变化 / 2 用法或文件错误。

--------------------------------------------------------------------------
两个容易搞错的地方（都实测踩过）
--------------------------------------------------------------------------
* **@keyframes 内部的关键帧选择器**（``0%, 33%`` / ``from`` / ``to``）不是页面选择器。
  关键帧定义本身不产生任何视觉效果，只有被 ``animation`` 引用时才生效，
  而引用它的那条规则带门控 ⇒ 必须排除，否则会误报「净新增」。
* **注释必须先剥**。解释性注释里的示范代码不是真规则。

--------------------------------------------------------------------------
它证明不了什么
--------------------------------------------------------------------------
只比 CSS。JS 行为变化（新增控件、改事件）不在范围内 ——
那需要真实浏览器验收。HTML 结构变化也不在范围内。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

DEFAULT_GATE = "data-ef-page"


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def styles_of(html: str) -> str:
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.S))


def rules_of(css: str):
    """产出 (选择器, [(属性, 值), ...])。跨行、多声明都能处理。"""
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", strip_comments(css)):
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


KEYFRAME_SEL = re.compile(
    r"(?:from|to|[\d.]+%)(?:\s*,\s*(?:from|to|[\d.]+%))*")


def triples(css: str, gate: str) -> set:
    """未装主题时**实际生效**的规则三元组。"""
    out = set()
    for sel, decls in rules_of(css):
        if gate in sel:
            continue                       # 门控规则：没装主题时不生效
        if KEYFRAME_SEL.fullmatch(sel):
            continue                       # 关键帧不是页面选择器
        for prop, value in decls:
            out.add((sel, prop, value))
    return out


CLAMP = re.compile(r"max\(\s*0px\s*,\s*(calc\(.*\))\s*\)")


def normalize(value: str) -> str:
    """把 max(0px, calc(X)) 归一成 calc(X)：正常令牌下两者等价。"""
    m = CLAMP.fullmatch(value.strip())
    return m.group(1) if m else value


def prove(before_css: str, after_css: str, gate: str):
    b = triples(before_css, gate)
    a = triples(after_css, gate)
    added_raw, removed_raw = a - b, b - a

    # 允许「仅 max() 包装」这一种差异：按 (选择器,属性) 配对后比归一值
    def key(t):
        return (t[0], t[1])

    add_by_key = {}
    for t in added_raw:
        add_by_key.setdefault(key(t), []).append(t)
    rem_by_key = {}
    for t in removed_raw:
        rem_by_key.setdefault(key(t), []).append(t)

    explained = []
    added, removed = set(added_raw), set(removed_raw)
    for k in list(add_by_key):
        if k not in rem_by_key:
            continue
        for ta in add_by_key[k]:
            for tr in rem_by_key[k]:
                if normalize(ta[2]) == normalize(tr[2]):
                    added.discard(ta)
                    removed.discard(tr)
                    explained.append({"selector": k[0], "prop": k[1],
                                      "before": tr[2], "after": ta[2]})
    return {
        "before_count": len(b),
        "after_count": len(a),
        "added": sorted(added),
        "removed": sorted(removed),
        "clamp_only": explained,
        "ok": not added and not removed,
    }


# ------------------------------------------------------------------ 自测

def selftest() -> int:
    cases = []

    def add(name, before, after, expect_ok, gate=DEFAULT_GATE):
        cases.append((name, before, after, expect_ok, gate))

    G = f"html[{DEFAULT_GATE}='on']"
    add("完全没改", ".a{color:red}", ".a{color:red}", True)
    add("只加门控规则", ".a{color:red}",
        f".a{{color:red}}\n{G} .a{{border-radius:0}}", True)
    add("门控规则改了已有属性也不算", ".a{border-radius:8px}",
        f".a{{border-radius:8px}}\n{G} .a{{border-radius:0}}", True)
    add("★ 无门控新增规则 → 必须报", ".a{color:red}",
        ".a{color:red}\n.b{color:blue}", False)
    add("★ 无门控删除规则 → 必须报", ".a{color:red}\n.b{color:blue}",
        ".a{color:red}", False)
    add("★ 无门控改值 → 必须报", ".a{color:red}", ".a{color:blue}", False)
    add("max() 包装算等价", ".a{border-radius:calc(var(--r) - 3px)}",
        ".a{border-radius:max(0px,calc(var(--r) - 3px))}", True)
    add("★ max() 里换了表达式 → 必须报",
        ".a{border-radius:calc(var(--r) - 3px)}",
        ".a{border-radius:max(0px,calc(var(--r) - 5px))}", False)
    add("★ 门控漏了一条 → 必须报", ".a{border-radius:8px}",
        f".a{{border-radius:8px}}\n{G} .a{{border-radius:0}}\n.b{{border-radius:0}}",
        False)
    add("关键帧不算净新增", ".a{color:red}",
        f".a{{color:red}}\n@keyframes k{{0%,33%{{opacity:1}}34%,100%{{opacity:.3}}}}\n"
        f"@media (prefers-reduced-motion: no-preference){{"
        f"{G} .a{{animation:k 1s infinite}}}}", True)
    add("关键帧 from/to 也不算", ".a{color:red}",
        f".a{{color:red}}\n@keyframes k{{from{{opacity:1}}to{{opacity:0}}}}", True)
    add("注释里的规则不算", ".a{color:red}",
        ".a{color:red}\n/* .b{color:blue} */", True)
    add("注释里的门控示范不算", ".a{color:red}",
        f".a{{color:red}}\n/* {G} .b{{border-radius:0}} */", True)
    add("多行选择器组", ".a{color:red}",
        f".a{{color:red}}\n{G} .x,\n{G} .y{{border-radius:0}}", True)
    add("自定义门控名", ".a{color:red}",
        ".a{color:red}\nhtml[data-my='on'] .a{border-radius:0}", True, "data-my")
    add("★ 自定义门控名下漏门控 → 必须报", ".a{color:red}",
        ".a{color:red}\nhtml[data-other='on'] .a{border-radius:0}", False, "data-my")

    passed = 0
    for name, before, after, expect_ok, gate in cases:
        r = prove(before, after, gate)
        good = r["ok"] == expect_ok
        print(("OK   " if good else "FAIL ") + name
              + ("" if good else f"  → ok={r['ok']} 期望 {expect_ok}；{r}"))
        passed += good
    print()
    print(f"{passed}/{len(cases)} 项通过")
    return 0 if passed == len(cases) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="机器证明「没装主题时页面外观不变」（零依赖）")
    ap.add_argument("before", nargs="?", help="改造前的 HTML")
    ap.add_argument("after", nargs="?", help="改造后的 HTML")
    ap.add_argument("--gate", default=DEFAULT_GATE,
                    help=f"门控属性名（默认 {DEFAULT_GATE}）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--selftest", action="store_true", help="跑脚本自测")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.before or not args.after:
        ap.print_usage()
        print("需要 BEFORE 与 AFTER 两个文件，或用 --selftest")
        return 2

    pb, pa = pathlib.Path(args.before), pathlib.Path(args.after)
    for p in (pb, pa):
        if not p.is_file():
            print(f"文件不存在: {p}")
            return 2

    result = prove(styles_of(pb.read_text(encoding="utf-8")),
                   styles_of(pa.read_text(encoding="utf-8")), args.gate)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    print(f"改造前生效规则 {result['before_count']} 条 / "
          f"改造后（剥门控）{result['after_count']} 条")
    if result["clamp_only"]:
        print(f"\n仅 max(0px,...) 包装（计算等价，允许）{len(result['clamp_only'])} 处：")
        for e in result["clamp_only"]:
            print(f"  {e['selector']} {e['prop']}: {e['before']} → {e['after']}")
    if result["added"]:
        print(f"\n★ 净新增 {len(result['added'])} 条（没装主题时也会生效）：")
        for s, p, v in result["added"]:
            print(f"  + {s} {{ {p}: {v} }}")
    if result["removed"]:
        print(f"\n★ 净删除 {len(result['removed'])} 条（没装主题时外观变了）：")
        for s, p, v in result["removed"]:
            print(f"  - {s} {{ {p}: {v} }}")
    print()
    if result["ok"]:
        print("证明成立：没装主题时的规则集零净变化。")
        return 0
    print("证明不成立：请给上面这些规则加门控，或说明它们为何应当无条件生效。")
    return 1


if __name__ == "__main__":
    sys.exit(main())