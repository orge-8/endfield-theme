# Changelog

## 0.2.0 (2026-11-22)

视觉强化（用户反馈「风格特征不够明显，等高线再明显一点，动画效果做了吗」）。

- 等高线底纹（此前完全缺失）：
  - 引入 endfield-ui-skill 的 contour-a/b.svg（skill 明示可自由使用），随注入分发进
    dist/fonts/endfield/，卸载/停用一并清理。
  - 铺在主区 [data-observation-shell]::before（z-index:0，内容 z-10 在其上，
    卡片不透明自然盖住，只在留白处露出）；右上/左下两角各一片，不闭合。
  - 浓度 --ef-contour = 墨色 18%（skill 基准 9%，按用户要求加倍）；跟随 --ef-ink
    自动适配明暗两套；移动端只保留右上一片（34rem）。
- 动效补齐（此前只有按钮擦入 + 对话框时长微调，原生 zoom-in-95 缩放弹出未压掉）：
  - 新增关键帧：通电 ef-power-on/off（clip-path 从上往下展开/关上）、
    擦入 ef-wipe-in/out、斜切快门 ef-shutter-in、逐行亮起 ef-come、线性淡入出。
  - 对话框/警报框：通电 280ms mech 开 / 180ms 关；移动端右抽屉改快门推入 360ms。
  - 下拉/弹出/选择浮层：通电 200/120ms；遮罩 200ms 线性淡入（不缩放）。
  - 提示条：左擦入 280ms / 右擦掉 160ms（黄旗语法不变）。
  - 标签页内容：逐行亮起 320ms snap；表格行 hover 右移 6px + 左色条落下
    （浅色=墨 / 深色=强调色，首格 ::before 实现，不依赖 tr box-shadow）。
  - 开关滑块/分段墨块/导航当前项：280ms mech 移动；主按钮按下擦入提速 100ms。
  - 全部动效包在 prefers-reduced-motion: no-preference 内，reduce 时全静止。
- 实测记录（2026-11-22）：门禁 PASS 3 / SKIP 0 / FAIL 0（静态 35 PASS / 1 WARN 属预期）；
  pytest 20 passed（新增等高线分发-清理闭环 + CSS 动效/等高线反向验证 2 例）；冒烟全过。
- 版本锚点同步 0.2.0；预览页重建（真实注入产物 + 对话框/提示条动效演示按钮）。

## 0.1.1 (2026-11-22)

修复：WebUI 配置页英文显示（用户真机反馈「配置页怎么都是英文」）。

- 根因（对照 SDK config.py 与 dashboard plugin-config.tsx 源码核实）：
  - 字段标签未声明 `json_schema_extra.label`，前端回退英文字段名 accent/paper/density；
  - 下拉选项显示名只认 `i18n["<locale>"]["choice:<枚举值>"]`，未声明时直接显示英文枚举值；
  - 字段级说明前端只渲染 `hint`，不渲染 `description`——原中文 description 根本没上页面。
- 修复：et_config.py 为 enabled/accent/paper/density 补中文 label + hint +
  zh-CN/en-US 双语 i18n（含全部 10 个选项显示名，如 lime→青柠（#B8FF3D））；
  两个配置节补 `__ui_i18n__` 与节 docstring。配置值本身保持英文枚举不变，
  et_variants.resolve 与既有 config.toml 零改动、零迁移。
- 实测记录（2026-11-22）：
  - 门禁 gate.sh：PASS 3 / SKIP 0 / FAIL 0（静态 PASS 35 / WARN 1 / FAIL 0，WARN 同 0.1.0 属预期）
  - pytest：18 passed（新增 test_config_schema_localized：直接调 SDK
    generate_plugin_config_schema 断言全部 label/hint/choice 中文，删任一声明即失败）
  - 冒烟：注入→幂等→热更新→停用移除→卸载还原 全过（版本锚点同步 0.1.1）
  - schema 直打核实：节标题「插件/外观」、字段「启用主题/强调色/纸色/密度」、
    10 个选项显示名全部中文。
- 版本锚点同步：_manifest.json / et_config.SUPPORTED_CONFIG_VERSION /
  tests 版本字符串 / README 配置表 → 0.1.1。

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
  - 真机版本核实（用户截图放大 + 用户确认）：**MaiBot 1.4.8**，一键包（MaiBotOneKey）
    部署，侧栏第二行 v0.9.2 为一键包版本。与本地实测基线完全一致。
  - min_version 保守放宽至 1.4.2：1.4.2 与 1.4.3 的 plugin_runtime 71 文件
    git blob sha 逐字节一致（含 loader 依赖链）；dashboard 1.10.2 的 observation
    选择器 / dashboard-button 类名 / html.dark 切换 / 行内 token 注入 /
    get_dist_path 与 1.10.8 全部一致。反向验证：ManifestValidator(host=1.4.2)
    对 min=1.4.3 报「Host 版本不兼容」拒载，min=1.4.2 errors=0。
- 已知边界：
  - CSS 选择器基于 dashboard 1.10.8（host 1.4.8 配套）源码核对；dashboard 大版本
    升级后若类名/结构变化需跟进维护。
  - 设计规则借鉴 endfield-ui-skill（无 LICENSE，仅借鉴规则与 token 数值），
    CSS 全部自行重写；Saira 字体 SIL OFL 可自由打包。
