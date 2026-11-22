"""endfield-theme 配置模型（独立模块，避免 plugin.py 过长）。

三个外观开关：accent / paper / density，全部是 Literal 枚举，
WebUI 配置页按枚举渲染下拉框。默认值对应「夜班」预设：
lime 强调色 + neutral 纸色 + compact 密度（深色模式下最协调）。
"""

from typing import Literal

from maibot_sdk import Field, PluginConfigBase

SUPPORTED_CONFIG_VERSION = "0.1.0"  # 与 _manifest.json 的 version 保持同步


class PluginSectionConfig(PluginConfigBase):
    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0

    enabled: bool = Field(default=True, description="是否启用主题（关闭后移除注入，恢复官方外观）")
    config_version: str = Field(
        default=SUPPORTED_CONFIG_VERSION,
        description="配置版本（与插件版本同步）",
        json_schema_extra={"hidden": True, "disabled": True},
    )


class AppearanceConfig(PluginConfigBase):
    """外观：三个开关决定主题变体。明暗两套跟随 WebUI 自身的深浅色设置。"""

    __ui_label__ = "外观"
    __ui_icon__ = "palette"
    __ui_order__ = 1

    accent: Literal["yellow", "lime", "ice", "amber"] = Field(
        default="lime",
        description=(
            "强调色：yellow(标准黄 #FFFA00) / lime(青柠 #B8FF3D) / "
            "ice(冰蓝 #7DE6FF) / amber(琥珀 #FFB31F)。"
            "只用于当前位置、可点击内容与醒目提醒的填充"
        ),
    )
    paper: Literal["neutral", "warm", "cool"] = Field(
        default="neutral",
        description=(
            "纸色：neutral(中性灰白) / warm(暖米色) / cool(冷青灰)。"
            "只影响背景、面板、细线与浅灰填充，文字墨色不变"
        ),
    )
    density: Literal["compact", "standard", "roomy"] = Field(
        default="compact",
        description=(
            "密度：compact(紧凑 0.9375) / standard(标准 1) / roomy(宽松 1.0625)。"
            "同时缩放字号与间距，点击区域不小于 44px"
        ),
    )


class EndfieldThemeConfig(PluginConfigBase):
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)
