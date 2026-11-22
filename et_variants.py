"""endfield-theme 变体定义：六个维度的取值表。

accent / paper / density / cut / ground / motion，对齐 endfield-ui-skill
references/variation.md 的六维变体。默认值 = 0.3.0 现状
（lime/neutral/compact/standard/contours/full），升级零外观变化。

数值来源：终末地风格设计语言（参考 endfield-ui-skill 的公开设计规则，
CSS 全部自行重写）。颜色为 sRGB hex；HSL 三元组供 dashboard 的
hsl(var(--color-*)) 消费管线使用。
"""

# 强调色：只做填充，上面的字用墨色（对比度均 >= 10:1）
ACCENTS = {
    "yellow": {"hex": "#FFFA00", "hsl": "59.6 100% 50%"},
    "lime": {"hex": "#B8FF3D", "hsl": "82.3 100% 62%"},
    "ice": {"hex": "#7DE6FF", "hsl": "191.9 100% 74.5%"},
    "amber": {"hex": "#FFB31F", "hsl": "39.6 100% 56.1%"},
}

# 纸色：只动 paper/panel/rule/chip 四项，ink/ink2 不变
PAPERS = {
    "neutral": {
        "light": {"paper": "#F4F4F2", "panel": "#FFFFFF", "rule": "#D9D9D6", "chip": "#E4E4E0"},
        "dark": {"paper": "#191919", "panel": "#222222", "rule": "#353535", "chip": "#2E2E2E"},
    },
    "warm": {
        "light": {"paper": "#F3F1EA", "panel": "#FFFEFA", "rule": "#DCD8CC", "chip": "#E7E3D8"},
        "dark": {"paper": "#1B1A17", "panel": "#24221E", "rule": "#38352F", "chip": "#302D28"},
    },
    "cool": {
        "light": {"paper": "#F0F3F5", "panel": "#FFFFFF", "rule": "#D3DADF", "chip": "#E0E6EA"},
        "dark": {"paper": "#171A1C", "panel": "#1F2326", "rule": "#323A3F", "chip": "#2A3034"},
    },
}

DENSITIES = {"compact": 0.9375, "standard": 1.0, "roomy": 1.0625}

# 切角幅度：所有切角一起缩放，含义不变（skill variation.md）
CUTS = {"tight": 0.6, "standard": 1.0, "wide": 1.6}

# 底纹：contours 等高线（默认）/ grid 网格 / hatch 斜线纹 / plain 无
GROUNDS = ("contours", "grid", "hatch", "plain")

# 动效：full 全开（默认）/ calm 去掉开页入场，保留回应操作与进出
MOTIONS = ("full", "calm")

# 不随变体走的固定色
INK_LIGHT = "#161616"
INK2_LIGHT = "#5C5C5C"
INK_DARK = "#EDEDED"
INK2_DARK = "#A3A3A3"
DANGER_LIGHT = "#B3261E"
DANGER_DARK = "#FF8A7A"
COMMAND_BAR = "#161616"  # 命令栏两套主题恒深色
TRI_A = "#FF00F0"
TRI_C = "#00FFA2"


def hex_to_hsl(hex_color: str) -> str:
    """#RRGGBB -> 'H S% L%'（dashboard 色彩管线的 HSL 三元组格式）。"""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        hue = sat = 0.0
    else:
        d = mx - mn
        sat = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r:
            hue = (g - b) / d + (6 if g < b else 0)
        elif mx == g:
            hue = (b - r) / d + 2
        else:
            hue = (r - g) / d + 4
        hue /= 6
    return f"{hue * 360:.1f} {sat * 100:.1f}% {l * 100:.1f}%"


def resolve(accent: str, paper: str, density: str,
            cut: str = "standard", ground: str = "contours",
            motion: str = "full") -> dict:
    """把六个开关解析成完整变体字典；非法值回退默认。

    默认值 = 0.3.0 现状（lime/neutral/compact/standard/contours/full），
    老配置升级后外观零变化。
    """
    accent = accent if accent in ACCENTS else "lime"
    paper = paper if paper in PAPERS else "neutral"
    density = density if density in DENSITIES else "compact"
    cut = cut if cut in CUTS else "standard"
    ground = ground if ground in GROUNDS else "contours"
    motion = motion if motion in MOTIONS else "full"
    return {
        "accent": accent,
        "paper": paper,
        "density": density,
        "cut": cut,
        "ground": ground,
        "motion": motion,
        "accentHex": ACCENTS[accent]["hex"],
        "accentHsl": ACCENTS[accent]["hsl"],
        "scale": DENSITIES[density],
        "cutK": CUTS[cut],
        "light": dict(PAPERS[paper]["light"]),
        "dark": dict(PAPERS[paper]["dark"]),
    }


def build_preamble(variant: dict) -> str:
    """生成注入样式块开头的变量声明（html 与 html.dark 两套）。

    dashboard 的主题管线把 token 写在 documentElement 的行内样式上，
    行内优先级高于样式表，所以这里全部用 !important 压过去。
    """
    a_hsl = variant["accentHsl"]
    a_hex = variant["accentHex"]
    scale = variant["scale"]

    def color_block(p: dict, ink: str, ink2: str, danger: str, trace_hsl: str,
                    primary_hsl: str) -> str:
        # 看板层（board.css）与外壳层（surfaces.css）另有一套变量，
        # 原生 --board-chart-1/2 = hsl(var(--primary)/0.7|0.3)，浅色 primary=墨
        # 会让首页柱图变成灰柱。图表是填充语义，改强调色 + 墨阶（不用红绿）。
        board = (
            f"--board-chart-1:{a_hex} !important;"
            f"--board-chart-2:color-mix(in srgb, {ink} 45%, transparent) !important;"
            f"--board-chart-grid:{p['rule']} !important;"
            f"--board-chart-axis:{p['rule']} !important;"
            f"--board-chart-ink:{ink2} !important;"
        )
        # primary 语义 = 可读的「品牌色」：dashboard 大量用 text-primary 渲染文字/图标
        # （运行中计数、当前 Bot 名、GATEWAY 路径等）。浅色纸面上强调色对比度约 1.1:1，
        # 故浅色 primary=墨色；深色纸面强调色可读，primary=强调色。
        # 强调色只做填充的部件（按钮/开关/进度条/当前导航）在 CSS 里直接用 --ef-accent。
        return (
            f"--color-background:{hex_to_hsl(p['paper'])} !important;"
            f"--color-foreground:{hex_to_hsl(ink)} !important;"
            f"--color-card:{hex_to_hsl(p['panel'])} !important;"
            f"--color-card-foreground:{hex_to_hsl(ink)} !important;"
            f"--color-popover:{hex_to_hsl(p['panel'])} !important;"
            f"--color-popover-foreground:{hex_to_hsl(ink)} !important;"
            f"--color-primary:{primary_hsl} !important;"
            f"--color-primary-foreground:{hex_to_hsl(INK_LIGHT)} !important;"
            f"--color-primary-gradient:none !important;"
            f"--color-secondary:{hex_to_hsl(p['chip'])} !important;"
            f"--color-secondary-foreground:{hex_to_hsl(ink)} !important;"
            f"--color-muted:{hex_to_hsl(p['chip'])} !important;"
            f"--color-muted-foreground:{hex_to_hsl(ink2)} !important;"
            f"--color-accent:{hex_to_hsl(p['chip'])} !important;"
            f"--color-accent-foreground:{hex_to_hsl(ink)} !important;"
            f"--color-destructive:{hex_to_hsl(danger)} !important;"
            f"--color-destructive-foreground:0 0% 100% !important;"
            f"--color-border:{hex_to_hsl(p['rule'])} !important;"
            f"--color-input:{hex_to_hsl(p['rule'])} !important;"
            f"--color-ring:{trace_hsl} !important;"
            f"--color-chart-1:{a_hsl} !important;"
            f"--color-chart-2:{hex_to_hsl(ink)} !important;"
            f"--color-chart-3:{hex_to_hsl(ink2)} !important;"
            f"--color-chart-4:{hex_to_hsl(p['rule'])} !important;"
            f"--color-chart-5:{hex_to_hsl(TRI_C)} !important;"
            + board
        )

    shared = (
        # 形状：圆角一律 0，阴影一律无
        "--visual-radius-sm:0px !important;--visual-radius-md:0px !important;"
        "--visual-radius-lg:0px !important;--visual-radius-xl:0px !important;"
        "--visual-radius-full:0px !important;"
        "--visual-shadow-sm:none !important;--visual-shadow-md:none !important;"
        "--visual-shadow-lg:none !important;--visual-shadow-xl:none !important;"
        "--visual-blur-sm:0px !important;--visual-blur-md:0px !important;"
        "--visual-blur-lg:0px !important;"
        # 字体：Saira 宽体拉丁 + 中文黑体；字号随密度缩放
        '--typography-font-family-base:"Saira","Noto Sans SC","Microsoft YaHei UI",system-ui,sans-serif !important;'
        f"--typography-font-size-xs:{0.75 * scale:.4f}rem !important;"
        f"--typography-font-size-sm:{0.875 * scale:.4f}rem !important;"
        f"--typography-font-size-base:{1 * scale:.4f}rem !important;"
        f"--typography-font-size-lg:{1.125 * scale:.4f}rem !important;"
        f"--typography-font-size-xl:{1.25 * scale:.4f}rem !important;"
        f"--typography-font-size-2xl:{1.5 * scale:.4f}rem !important;"
        "--typography-font-weight-normal:400 !important;"
        "--typography-font-weight-medium:600 !important;"
        "--typography-font-weight-semibold:700 !important;"
        "--typography-font-weight-bold:700 !important;"
        "--typography-letter-spacing-wide:0.14em !important;"
        # 间距随密度缩放
        f"--layout-space-xs:{0.5 * scale:.4f}rem !important;"
        f"--layout-space-sm:{0.75 * scale:.4f}rem !important;"
        f"--layout-space-md:{1 * scale:.4f}rem !important;"
        f"--layout-space-lg:{1.5 * scale:.4f}rem !important;"
        f"--layout-space-xl:{2 * scale:.4f}rem !important;"
        f"--layout-space-2xl:{3 * scale:.4f}rem !important;"
        # 动效：短硬机械，snap 出现 / mech 退出
        "--animation-anim-duration-fast:100ms !important;"
        "--animation-anim-duration-normal:200ms !important;"
        "--animation-anim-duration-slow:320ms !important;"
        "--animation-anim-easing-default:cubic-bezier(0.2,0.7,0.1,1) !important;"
        "--animation-anim-easing-in:cubic-bezier(0.7,0,0.2,1) !important;"
        "--animation-anim-easing-out:cubic-bezier(0.16,1,0.3,1) !important;"
        "--animation-anim-easing-in-out:cubic-bezier(0.7,0,0.2,1) !important;"
        # 看板层：麦麦观察首页 / 机器人管理 / 桌宠页共用（board.css）。
        # 原生 module-radius 0.75rem + 双层投影、number/code-font inherit，
        # 这里直角细线 + Saira 宽体数字与代号。
        "--board-module-radius:0px !important;"
        "--board-module-shadow:none !important;"
        "--board-module-border:1px solid var(--ef-rule) !important;"
        "--board-module-bg:var(--ef-panel) !important;"
        "--board-screen-radius:0px !important;"
        "--board-screen-shadow:none !important;"
        "--board-screen-border:0 !important;"
        "--board-shadow:none !important;"
        "--board-border:0 !important;"
        "--board-bg:transparent !important;"
        "--board-rule:1px solid var(--ef-rule) !important;"
        "--board-ink:var(--ef-ink) !important;"
        "--board-dim:var(--ef-ink2) !important;"
        # 链接/引号等文字语义：浅色=墨（强调色白底不可读），深色块改成强调色
        "--board-accent:var(--ef-ink) !important;"
        '--board-number-font:"Saira","Noto Sans SC","Microsoft YaHei UI",system-ui,sans-serif !important;'
        '--board-code-font:"Saira","Noto Sans SC","Microsoft YaHei UI",system-ui,sans-serif !important;'
        # 公共外壳层（surfaces.css）：页面框 / 数据屏 / 列表选中
        "--surface-radius:0px !important;"
        "--surface-frame-shadow:none !important;"
        "--surface-data-shadow:none !important;"
        "--surface-texture:none !important;"
        "--surface-data-texture:none !important;"
        "--surface-data-stroke:1px !important;"
        "--surface-separator-stroke:1px !important;"
        "--surface-frame-bg:var(--ef-panel) !important;"
        "--surface-data-bg:var(--ef-paper) !important;"
        "--surface-line:var(--ef-rule) !important;"
        "--surface-ink:var(--ef-ink) !important;"
        "--surface-focus:var(--ef-ink) !important;"
        "--list-selected-bg:var(--ef-accent) !important;"
        "--list-selected-ink:#161616 !important;"
        "--list-hover-bg:var(--ef-chip) !important;"
        # 首页专属（observation.css）：标题字体、编辑态描线
        '--obs-heading-font:"Saira","Noto Sans SC","Microsoft YaHei UI",system-ui,sans-serif !important;'
        '--obs-plate-font:"Saira","Noto Sans SC","Microsoft YaHei UI",system-ui,sans-serif !important;'
        "--obs-edit:var(--ef-ink) !important;"
        # 聊天气泡：直角、无投影；发出方=强调色填充 + 墨字
        "--chat-bubble-radius:0px !important;"
        "--chat-bubble-shadow:none !important;"
        "--chat-bubble-bg:var(--ef-chip) !important;"
        "--chat-bubble-ink:var(--ef-ink) !important;"
        "--chat-outgoing-bg:var(--ef-accent) !important;"
        "--chat-outgoing-ink:#161616 !important;"
        # 本主题自有变量
        f"--ef-accent:{a_hex};"
        f"--ef-accent-hsl:{a_hsl};"
        f"--ef-ink:{INK_LIGHT};--ef-ink2:{INK2_LIGHT};"
        f"--ef-paper:{variant['light']['paper']};--ef-panel:{variant['light']['panel']};"
        f"--ef-rule:{variant['light']['rule']};--ef-chip:{variant['light']['chip']};"
        f"--ef-danger:{DANGER_LIGHT};"
        f"--ef-command-bar:{COMMAND_BAR};"
        f"--ef-tri-a:{TRI_A};--ef-tri-c:{TRI_C};"
        f"--ef-scale:{scale};"
        # 切角幅度：所有切角一起缩放（tight ×0.6 / standard ×1 / wide ×1.6）
        f"--ef-cut-k:{variant['cutK']};"
        f"--ef-cut-sm:{7 * variant['cutK']:g}px;"
        f"--ef-cut-btn:{8 * variant['cutK']:g}px;"
        f"--ef-cut-panel:{26 * variant['cutK']:g}px;"
        f"--ef-cut-badge:{5 * variant['cutK']:g}px;"
        f"--ef-cut-action:{4 * variant['cutK']:g}px;"
        "--ef-snap:cubic-bezier(0.16,1,0.3,1);"
        "--ef-mech:cubic-bezier(0.7,0,0.2,1);"
        "--ef-ease:cubic-bezier(0.2,0.7,0.1,1);"
        # 等高线底纹：墨色 18%（skill 基准 9%，按用户要求加强；只铺两角不闭合）
        "--ef-contour:color-mix(in srgb, var(--ef-ink) 18%, transparent);"
        # 斜线纹（ground=hatch 与处理中/禁用共用）：45° 墨色 22%
        "--ef-hatch:repeating-linear-gradient(-45deg, transparent 0 5px,"
        "color-mix(in srgb, var(--ef-ink) 22%, transparent) 5px 6.5px);"
    )
    # primary：浅色=墨（text-primary 文字可读），深色=强调色（深底上可读）
    light = color_block(variant["light"], INK_LIGHT, INK2_LIGHT, DANGER_LIGHT,
                        hex_to_hsl(INK_LIGHT), hex_to_hsl(INK_LIGHT))
    dark = color_block(variant["dark"], INK_DARK, INK2_DARK, DANGER_DARK, a_hsl, a_hsl)
    dark_own = (
        f"--ef-ink:{INK_DARK};--ef-ink2:{INK2_DARK};"
        f"--ef-paper:{variant['dark']['paper']};--ef-panel:{variant['dark']['panel']};"
        f"--ef-rule:{variant['dark']['rule']};--ef-chip:{variant['dark']['chip']};"
        f"--ef-danger:{DANGER_DARK};"
        # 深色纸面上强调色可读，链接/引号等文字语义直接用强调色
        "--board-accent:var(--ef-accent) !important;"
        "--surface-focus:var(--ef-accent) !important;"
        "--obs-edit:var(--ef-accent) !important;"
    )
    return (
        f"html{{{light}{shared}}}\n"
        f"html.dark{{{dark}{dark_own}}}\n"
    )


def variant_attrs(variant: dict) -> str:
    """html 标签上的变体属性（ground/motion 由 CSS 按属性选择器消费）。

    由 plugin.py 注入时写到 <html> 上；让位层不影响这两个属性本身。
    """
    return (
        f' data-ef-ground="{variant["ground"]}"'
        f' data-ef-motion="{variant["motion"]}"'
    )
