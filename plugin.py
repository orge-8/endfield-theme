"""终末地风格 WebUI 主题：往 dashboard 的 index.html 注入样式与字体。

L2 注入式：不改 JS 构建产物、不改资产文件名，只注入一段受控样式块
（token 覆盖 + 部件皮肤）和一个字体 link。dashboard 升级后重新注入即可。
三个外观开关 accent / paper / density 在 WebUI 插件配置页调整，热更新即时重注入。
"""

import logging
import re
from pathlib import Path
from typing import Any, ClassVar

from maibot_sdk import MaiBotPlugin, PluginConfigBase
from maibot_sdk.types import CONFIG_RELOAD_SCOPE_SELF

try:
    from .et_config import SUPPORTED_CONFIG_VERSION, EndfieldThemeConfig
    from .et_variants import build_preamble, resolve
except ImportError:  # 平铺加载兜底（真机 Runner 是包式加载）
    from et_config import SUPPORTED_CONFIG_VERSION, EndfieldThemeConfig
    from et_variants import build_preamble, resolve

# 配置模型在 et_config.py：PluginSectionConfig 内含 config_version 字段，
# 默认值取 SUPPORTED_CONFIG_VERSION，与 _manifest.json 的 version 保持同步。
# 配置版本锚点：与 et_config.SUPPORTED_CONFIG_VERSION / _manifest.json version 同步。
# 运行时自检配置模型确实携带该字段（Runner 硬性要求）。
EXPECTED_CONFIG_VERSION = SUPPORTED_CONFIG_VERSION  # config_version = 插件版本
_PLUGIN_DEFAULTS = EndfieldThemeConfig().model_dump()["plugin"]
assert _PLUGIN_DEFAULTS["config_version"] == EXPECTED_CONFIG_VERSION, \
    "plugin.config_version 与插件版本不同步"

logger = logging.getLogger(__name__)

STYLE_ID = "endfield-theme-style"
FONT_LINK_ID = "endfield-theme-fonts"
STYLE_RE = re.compile(rf"\n?<style id=\"{STYLE_ID}\"[^>]*>.*?</style>", re.S)
FONT_LINK_RE = re.compile(rf"\n?<link id=\"{FONT_LINK_ID}\"[^>]*>")

ASSET_DIR = Path(__file__).parent / "theme"
CSS_FILE = ASSET_DIR / "endfield-theme.css"
FONTS_CSS_FILE = ASSET_DIR / "fonts.css"
FONTS_SRC = Path(__file__).parent / "fonts"


class EndfieldThemePlugin(MaiBotPlugin):
    """管理 index.html 里的主题样式块与字体链接。"""

    config_model: ClassVar[type[PluginConfigBase] | None] = EndfieldThemeConfig

    async def on_load(self) -> None:
        self._apply()

    async def on_unload(self) -> None:
        removed = self._remove()
        self.ctx.logger.info("[endfield-theme] 卸载完成，移除注入=%s；请刷新 WebUI", removed)

    async def on_config_update(self, scope: str, config_data: dict[str, Any], version: str) -> None:
        del config_data, version
        if scope == CONFIG_RELOAD_SCOPE_SELF:
            self._apply()

    # ------------------------------------------------------------------ 内部

    def _dist_index(self) -> Path:
        from maibot_dashboard import get_dist_path

        return Path(get_dist_path()).resolve() / "index.html"

    def _variant(self) -> dict:
        ap = self.config.appearance
        return resolve(ap.accent, ap.paper, ap.density)

    def _build_style(self, variant: dict) -> str:
        """样式块：变量 preamble（压行内 token）+ 字体声明 + 部件皮肤。"""
        return (
            build_preamble(variant)
            + FONTS_CSS_FILE.read_text(encoding="utf-8")
            + "\n"
            + CSS_FILE.read_text(encoding="utf-8")
        )

    def _install_fonts(self, dist: Path) -> bool:
        """把 Saira 字体拷进 dashboard 静态目录（只动本插件自己的子目录）。"""
        src = FONTS_SRC / "Saira.ttf"
        if not src.is_file():
            return False
        dst_dir = dist / "fonts" / "endfield"
        dst_dir.mkdir(parents=True, exist_ok=True)
        for name in ("Saira.ttf", "Saira-OFL.txt"):
            item = FONTS_SRC / name
            if not item.is_file():
                continue
            target = dst_dir / name
            if target.exists() and target.stat().st_size == item.stat().st_size:
                continue
            target.write_bytes(item.read_bytes())
        return True

    def _uninstall_fonts(self, dist: Path) -> None:
        target = dist / "fonts" / "endfield"
        if not target.is_dir():
            return
        for item in target.iterdir():
            if item.is_file() and item.name in {"Saira.ttf", "Saira-OFL.txt", "fonts.css"}:
                item.unlink(missing_ok=True)
        try:
            target.rmdir()
        except OSError:
            pass

    def _apply(self) -> None:
        try:
            index = self._dist_index()
        except Exception as exc:
            self.ctx.logger.warning("[endfield-theme] 无法定位 dashboard dist：%s", exc)
            return
        if not index.is_file():
            self.ctx.logger.warning("[endfield-theme] 找不到 dashboard 的 index.html：%s", index)
            return

        html = index.read_text(encoding="utf-8")
        html_without = FONT_LINK_RE.sub("", STYLE_RE.sub("", html))

        if not self.config.plugin.enabled:
            if html_without != html:
                index.write_text(html_without, encoding="utf-8")
                self._uninstall_fonts(index.parent)
                self.ctx.logger.info("[endfield-theme] 插件已停用，注入内容已移除")
            return

        if "</head>" not in html_without:
            self.ctx.logger.warning("[endfield-theme] index.html 缺少 </head>，跳过注入")
            return

        variant = self._variant()
        style_tag = (
            f'\n<style id="{STYLE_ID}" data-plugin="github.orge-8.endfield-theme">\n'
            f"{self._build_style(variant)}</style>"
        )
        font_link = ""
        if self._install_fonts(index.parent):
            font_link = f'\n<link id="{FONT_LINK_ID}" rel="stylesheet" href="/fonts/endfield/fonts.css">'
            # fonts.css 也要进 dist（@font-face 声明）
            dst_css = index.parent / "fonts" / "endfield" / "fonts.css"
            src_css = FONTS_CSS_FILE.read_text(encoding="utf-8")
            if not dst_css.exists() or dst_css.read_text(encoding="utf-8") != src_css:
                dst_css.write_text(src_css, encoding="utf-8")
        updated = html_without.replace("</head>", f"{font_link}{style_tag}</head>", 1)

        if updated == html:
            self.ctx.logger.info("[endfield-theme] 注入内容已是最新")
            return
        index.write_text(updated, encoding="utf-8")
        self.ctx.logger.info(
            "[endfield-theme] 主题已注入（accent=%s paper=%s density=%s）",
            variant["accent"], variant["paper"], variant["density"],
        )

    def _remove(self) -> bool:
        try:
            index = self._dist_index()
        except Exception:
            return False
        if not index.is_file():
            return False
        html = index.read_text(encoding="utf-8")
        cleaned = FONT_LINK_RE.sub("", STYLE_RE.sub("", html))
        self._uninstall_fonts(index.parent)
        if cleaned == html:
            return False
        index.write_text(cleaned, encoding="utf-8")
        return True


def create_plugin() -> EndfieldThemePlugin:
    """Runner 加载入口。"""
    return EndfieldThemePlugin()
