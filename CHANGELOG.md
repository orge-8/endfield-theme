# Changelog

## 0.1.0 (2026-11-22)

首个版本：终末地风格 WebUI 主题（L2 注入式）。

- 注入机制：往 dashboard dist 的 index.html 注入受控样式块（token 覆盖 + 部件皮肤）
  与字体 link；不改 JS 构建产物；卸载/停用正则移除并还原官方 index.html。
- 三个外观开关（WebUI 插件配置页，热更新即时重注入）：
  - accent：yellow / lime / ice / amber（默认 lime）
  - paper：neutral / warm / cool（默认 neutral）
  - density：compact / standard / roomy（默认 compact）
- 设计语法：单一强调色只做填充、切角=可点击（clip-path）、圆角/阴影/毛玻璃全零、
  1px 细线分区、侧栏深色命令栏（两套主题恒 #161616）、当前导航项强调色整块+切角、
  主按钮悬停黄色擦入（触屏静止即黄底）、分段选择当前段墨底反白、红色只给删除、
  提示条黄旗不用红、短硬机械动效（snap/mech/ease）、prefers-reduced-motion 全静止。
- 明暗两套完整主题，跟随 WebUI 自身深浅色设置（html.dark）。
- 字体：Saira 可变字体（wdth 50-125 / wght 100-900，SIL OFL 1.1，许可证随附），
  自托管进 dist/fonts/endfield/；中文落 Noto Sans SC / 微软雅黑。
- 实测记录（2026-11-22）：
  - 门禁 gate.sh：PASS 3 / SKIP 0 / FAIL 0（静态 PASS 35 / WARN 1 / FAIL 0；
    WARN 为「无组件装饰器」——纯注入插件无 Command/Tool/Hook，属预期）
  - 冒烟：注入→幂等→热更新→停用移除→卸载还原 全过
  - pytest：17 passed（变体解析 4 / preamble 4 / 注入闭环 9）
  - PluginLoader 加载探针：MaiBot-host-1.4.8 源码，host 1.4.2~1.4.8 / sdk 2.23.0，
    加载成功 1 插件、instance=yes、失败 0
  - 环境：devkit .venv SDK 2.23.0（与 PyPI 官方最新一致）
  - 官方最新版已核实（2026-11-22 17:43）：MaiBot v1.4.8（2026-11-20 发布），
    max_version=1.4.8 即官方最新，无需再放宽。
  - 真机版本核实（用户截图）：MaiBot 1.4.2 + WebUI 1.10.2。
    兼容性证据：1.4.2 与 1.4.3 的 plugin_runtime 71 文件 git blob sha 逐字节一致
    （含 loader 依赖链）；dashboard 1.10.2 的 observation 选择器 / dashboard-button
    类名 / html.dark 切换 / 行内 token 注入 / get_dist_path 与 1.10.8 全部一致。
    min_version 由 1.4.3 降为 1.4.2（反向验证：min=1.4.3 时 host 1.4.2 报
    「Host 版本不兼容」拒载；min=1.4.2 时 errors=0）。
- 已知边界：
  - CSS 选择器基于 dashboard 1.10.8（host 1.4.8 配套）源码核对；dashboard 大版本
    升级后若类名/结构变化需跟进维护。
  - 设计规则借鉴 endfield-ui-skill（无 LICENSE，仅借鉴规则与 token 数值），
    CSS 全部自行重写；Saira 字体 SIL OFL 可自由打包。
