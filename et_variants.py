"""endfield-theme 变体定义：accent / paper / density 三个维度的取值表。

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


def resolve(accent: str, paper: str, density: str) -> dict:
    """把三个开关解析成完整变体字典；非法值回退默认（lime/neutral/compact）。"""
    accent = accent if accent in ACCENTS else "lime"
    paper = paper if paper in PAPERS else "neutral"
    density = density if density in DENSITIES else "compact"
    return {
        "accent": accent,
        "paper": paper,
        "density": density,
        "accentHex": ACCENTS[accent]["hex"],
        "accentHsl": ACCENTS[accent]["hsl"],
        "scale": DENSITIES[density],
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

    def color_block(p: dict, ink: str, ink2: str, danger: str, trace_hsl: str) -> str:
        return (
            f"--color-background:{hex_to_hsl(p['paper'])} !important;"
            f"--color-foreground:{hex_to_hsl(ink)} !important;"
            f"--color-card:{hex_to_hsl(p['panel'])} !important;"
            f"--color-card-foreground:{hex_to_hsl(ink)} !important;"
            f"--color-popover:{hex_to_hsl(p['panel'])} !important;"
            f"--color-popover-foreground:{hex_to_hsl(ink)} !important;"
            f"--color-primary:{a_hsl} !important;"
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
        "--ef-cut-sm:7px;--ef-cut-btn:8px;--ef-cut-panel:26px;"
        "--ef-snap:cubic-bezier(0.16,1,0.3,1);"
        "--ef-mech:cubic-bezier(0.7,0,0.2,1);"
        "--ef-ease:cubic-bezier(0.2,0.7,0.1,1);"
        # 等高线底纹：墨色 18%（skill 基准 9%，按用户要求加强；只铺两角不闭合）
        "--ef-contour:color-mix(in srgb, var(--ef-ink) 18%, transparent);"
    )
    light = color_block(variant["light"], INK_LIGHT, INK2_LIGHT, DANGER_LIGHT,
                        hex_to_hsl(INK_LIGHT))
    dark = color_block(variant["dark"], INK_DARK, INK2_DARK, DANGER_DARK, a_hsl)
    dark_own = (
        f"--ef-ink:{INK_DARK};--ef-ink2:{INK2_DARK};"
        f"--ef-paper:{variant['dark']['paper']};--ef-panel:{variant['dark']['panel']};"
        f"--ef-rule:{variant['dark']['rule']};--ef-chip:{variant['dark']['chip']};"
        f"--ef-danger:{DANGER_DARK};"
    )
    return (
        f"html{{{light}{shared}}}\n"
        f"html.dark{{{dark}{dark_own}}}\n"
    )
