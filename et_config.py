"""endfield-theme 配置模型（独立模块，避免 plugin.py 过长）。

六个外观开关：accent / paper / density / cut / ground / motion，
全部是 Literal 枚举，WebUI 配置页按枚举渲染下拉框。
默认值 = 0.3.0 现状（lime/neutral/compact/standard/contours/full），
升级零外观变化；前三项默认对应「夜班」预设的深色协调组合。

WebUI 中文化约定（对照 SDK config.py 与 dashboard plugin-config.tsx 源码核实）：
- 字段标签：json_schema_extra 的 "label"（未声明时前端回退英文字段名）；
- 下拉选项显示名：json_schema_extra 的 "i18n"，键 "choice:<枚举值>"；
- 字段说明文字：前端只渲染 hint，不渲染 description，故说明放 "hint"；
- i18n locale 用 zh-CN / en-US（前端 getLocaleCandidates 对 zh/en 均兼容）。
配置值本身保持英文枚举（yellow/lime/...），与 et_variants.resolve 的键一致。
"""

from typing import Literal

from maibot_sdk import Field, PluginConfigBase

SUPPORTED_CONFIG_VERSION = "0.4.0"  # 与 _manifest.json 的 version 保持同步


class PluginSectionConfig(PluginConfigBase):
    """插件启用状态与配置版本。"""

    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0
    __ui_i18n__ = {
        "zh-CN": {"title": "插件", "description": "插件启用状态与配置版本。"},
        "en-US": {"title": "Plugin", "description": "Plugin enable state and config version."},
    }

    enabled: bool = Field(
        default=True,
        description="是否启用主题（关闭后移除注入，恢复官方外观）",
        json_schema_extra={
            "label": "启用主题",
            "hint": "关闭后移除注入，恢复官方外观",
            "i18n": {
                "zh-CN": {"label": "启用主题", "hint": "关闭后移除注入，恢复官方外观"},
                "en-US": {
                    "label": "Enable theme",
                    "hint": "Removes the injection and restores the official look when off",
                },
            },
        },
    )
    config_version: str = Field(
        default=SUPPORTED_CONFIG_VERSION,
        description="配置版本（与插件版本同步）",
        json_schema_extra={"hidden": True, "disabled": True},
    )


class AppearanceConfig(PluginConfigBase):
    """外观：六个开关决定主题变体。明暗两套跟随 WebUI 自身的深浅色设置。

    官方界面风格选「千禧 / 未来复古」时主题整体让位（界面回到官方原样），
    切回「现代」自动恢复，无需重启。
    """

    __ui_label__ = "外观"
    __ui_icon__ = "palette"
    __ui_order__ = 1
    __ui_i18n__ = {
        "zh-CN": {
            "title": "外观",
            "description": "六个开关决定主题变体。明暗跟随 WebUI 设置；官方风格选千禧/未来复古时主题让位。",
        },
        "en-US": {
            "title": "Appearance",
            "description": "Six switches select the variant. Light/dark follows the WebUI; the theme yields under Millennium/Future-Retro styles.",
        },
    }

    accent: Literal["yellow", "lime", "ice", "amber"] = Field(
        default="lime",
        description=(
            "强调色：yellow(标准黄 #FFFA00) / lime(青柠 #B8FF3D) / "
            "ice(冰蓝 #7DE6FF) / amber(琥珀 #FFB31F)。"
            "只用于当前位置、可点击内容与醒目提醒的填充"
        ),
        json_schema_extra={
            "label": "强调色",
            "hint": "只用于当前位置、可点击内容与醒目提醒的填充",
            "i18n": {
                "zh-CN": {
                    "label": "强调色",
                    "hint": "只用于当前位置、可点击内容与醒目提醒的填充",
                    "choice:yellow": "标准黄（#FFFA00）",
                    "choice:lime": "青柠（#B8FF3D）",
                    "choice:ice": "冰蓝（#7DE6FF）",
                    "choice:amber": "琥珀（#FFB31F）",
                },
                "en-US": {
                    "label": "Accent",
                    "hint": "Fills only the current location, clickable items and alerts",
                    "choice:yellow": "Standard yellow (#FFFA00)",
                    "choice:lime": "Lime (#B8FF3D)",
                    "choice:ice": "Ice blue (#7DE6FF)",
                    "choice:amber": "Amber (#FFB31F)",
                },
            },
        },
    )
    paper: Literal["neutral", "warm", "cool"] = Field(
        default="neutral",
        description=(
            "纸色：neutral(中性灰白) / warm(暖米色) / cool(冷青灰)。"
            "只影响背景、面板、细线与浅灰填充，文字墨色不变"
        ),
        json_schema_extra={
            "label": "纸色",
            "hint": "只影响背景、面板、细线与浅灰填充，文字墨色不变",
            "i18n": {
                "zh-CN": {
                    "label": "纸色",
                    "hint": "只影响背景、面板、细线与浅灰填充，文字墨色不变",
                    "choice:neutral": "中性灰白",
                    "choice:warm": "暖米色",
                    "choice:cool": "冷青灰",
                },
                "en-US": {
                    "label": "Paper",
                    "hint": "Affects backgrounds, panels, hairlines and light fills only; ink stays",
                    "choice:neutral": "Neutral gray-white",
                    "choice:warm": "Warm beige",
                    "choice:cool": "Cool gray-blue",
                },
            },
        },
    )
    density: Literal["compact", "standard", "roomy"] = Field(
        default="compact",
        description=(
            "密度：compact(紧凑 0.9375) / standard(标准 1) / roomy(宽松 1.0625)。"
            "同时缩放字号与间距，点击区域不小于 44px"
        ),
        json_schema_extra={
            "label": "密度",
            "hint": "同时缩放字号与间距，点击区域不小于 44px",
            "i18n": {
                "zh-CN": {
                    "label": "密度",
                    "hint": "同时缩放字号与间距，点击区域不小于 44px",
                    "choice:compact": "紧凑（0.9375）",
                    "choice:standard": "标准（1）",
                    "choice:roomy": "宽松（1.0625）",
                },
                "en-US": {
                    "label": "Density",
                    "hint": "Scales font sizes and spacing; hit targets stay >= 44px",
                    "choice:compact": "Compact (0.9375)",
                    "choice:standard": "Standard (1)",
                    "choice:roomy": "Roomy (1.0625)",
                },
            },
        },
    )


    cut: Literal["tight", "standard", "wide"] = Field(
        default="standard",
        description=(
            "切角幅度：tight(收紧 ×0.6) / standard(标准 ×1) / wide(放宽 ×1.6)。"
            "所有切角一起缩放，切角=可点击的含义不变"
        ),
        json_schema_extra={
            "label": "切角幅度",
            "hint": "所有切角一起缩放，切角=可点击的含义不变",
            "i18n": {
                "zh-CN": {
                    "label": "切角幅度",
                    "hint": "所有切角一起缩放，切角=可点击的含义不变",
                    "choice:tight": "收紧（×0.6）",
                    "choice:standard": "标准（×1）",
                    "choice:wide": "放宽（×1.6）",
                },
                "en-US": {
                    "label": "Corner cut",
                    "hint": "Scales every cut corner together; cut = pressable stays",
                    "choice:tight": "Tight (×0.6)",
                    "choice:standard": "Standard (×1)",
                    "choice:wide": "Wide (×1.6)",
                },
            },
        },
    )
    ground: Literal["contours", "grid", "hatch", "plain"] = Field(
        default="contours",
        description=(
            "底纹：contours(等高线) / grid(网格) / hatch(斜线纹) / plain(无)。"
            "只铺在主区留白处，极淡，随明暗自动适配"
        ),
        json_schema_extra={
            "label": "底纹",
            "hint": "只铺在主区留白处，极淡，随明暗自动适配",
            "i18n": {
                "zh-CN": {
                    "label": "底纹",
                    "hint": "只铺在主区留白处，极淡，随明暗自动适配",
                    "choice:contours": "等高线",
                    "choice:grid": "网格",
                    "choice:hatch": "斜线纹",
                    "choice:plain": "无",
                },
                "en-US": {
                    "label": "Ground",
                    "hint": "Faint texture in the main area margins only; follows light/dark",
                    "choice:contours": "Contours",
                    "choice:grid": "Grid",
                    "choice:hatch": "Hatching",
                    "choice:plain": "None",
                },
            },
        },
    )
    motion: Literal["full", "calm"] = Field(
        default="full",
        description=(
            "动效：full(全开) / calm(平静：去掉打开页面/浮层的入场，"
            "保留回应操作与退出)。系统「减少动态效果」开启时两者都全静止"
        ),
        json_schema_extra={
            "label": "动效",
            "hint": "平静档去掉开页入场，保留回应操作与退出",
            "i18n": {
                "zh-CN": {
                    "label": "动效",
                    "hint": "平静档去掉开页入场，保留回应操作与退出",
                    "choice:full": "全开",
                    "choice:calm": "平静",
                },
                "en-US": {
                    "label": "Motion",
                    "hint": "Calm drops open-page entrances; responses and exits stay",
                    "choice:full": "Full",
                    "choice:calm": "Calm",
                },
            },
        },
    )


class EndfieldThemeConfig(PluginConfigBase):
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)
