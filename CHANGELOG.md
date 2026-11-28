# Changelog

## 0.5.5 (2026-11-28)

插件卡右下切角重做，以及「已安装」徽章仍然只露一半。

### A. 切角不再用 clip-path

- `clip-path` 裁的是整个元素盒子，斜边处**没有描边**：右边框和下边框在切口突然断掉，
  看起来像「被啃掉一角」，而不是切角。
- 改用「与页面同色的三角遮罩 + 斜边 1px 细线」：
  - `::after` 26×26（跟随 `--ef-cut-panel`），`right/bottom: -1px` 盖住卡片边框角；
  - 两层 `linear-gradient(to bottom right, …)`：一层铺 `--ef-paper` 盖出三角，
    一层在 50% 处画 `--ef-rule` 1px 线，边框沿斜边收口；
  - `pointer-events: none`，不影响整卡点击。

### B. 「已安装」徽章的位移不在徽章身上

- 宿主结构是 `<div class="absolute left-4 top-0 -translate-y-1/2">…<span data-plugin-installed-badge>`，
  `-translate-y-1/2` 写在**父级容器**上，只清 span 的 `translate` 没有作用。
- 补 `[data-plugin-market-card] div:has(> [data-plugin-installed-badge])` 一并清零。
- 真机实测：`installed.y = 841 / card.y = 840`（此前是 829，被顶出 11px）。

### 验证

- pytest：**76 passed**（切角用例改为断言遮罩 + 斜边线，新增父级位移断言）。
- 真机：左右徽章 `inside: true`，growth 黄底、installed 墨底，
  切角斜边有 1px 线、三角与页面底色一致。
- 门禁：**PASS 3 / SKIP 0 / FAIL 0**。

## 0.5.4 (2026-11-28)

插件市场的榜单/已安装徽章只显示一半。

### 原因

- 宿主把徽章做成跨边框贴纸：`top-0` + `-translate-y-1/2`，一半压在卡片上边框外侧。
- 0.5.0 给可点击的插件卡加了右下切角 `clip-path`。`clip-path` 裁的是**整个元素盒子**，
  卡片外的子元素一并被裁 —— 徽章露在外面的上半截直接消失，只剩卡片内的下半截。
- 另外 Tailwind v4 的 `-translate-y-1/2` 走独立 `translate` 属性，
  只写 `transform: none` 压不住它（0.5.4 首次尝试就是因此无效）。

### 改法

- 徽章收回卡片内：`top: 0`、`transform: none`、`translate: none` 三个一起清，
  变成卡片右上（右上角不切）的内嵌角标，不再被裁。
- 卡片 `padding-top: 2.25rem`，给徽章 25px 高度让位，标题不被压住。
- 右下切角保留（切角=可点击的语法不变），只是裁不到任何跨出去的子元素了。

### 验证

- 真机量到 `badge.y = 177`、`card.y = 176`（`inside: true`），
  徽章 87×25 完整，标题 `y = 241` 不重叠。
- pytest：**76 passed**（新增 1 条：内嵌位置、`translate` 清零、顶部留白、切角保留）。
- 门禁：**PASS 3 / SKIP 0 / FAIL 0**。

## 0.5.3 (2026-11-28)

页面重载时居中的加载指示（`ThinkingIllustration`，三个点）重做。

### 现状为什么难看

真机量到的三条叠加：

1. 该组件也是 `role="status"`，被 0.5.0 的提示条规则当成 toast，套上
   「51px 深底 + 1px 细框 + 4px 左侧竖旗」——加载指示外面多了一个小黑条；
2. `.animate-bounce` 被主题统一停表（本来是给重启遮罩的装饰粒子做的），
   三点**完全不动**；
3. 圆点已被全局直角化，但三个静止方块套在框里，读不出在加载。

### 改法

- 只挑「含 `.animate-bounce` 子元素」的 `role=status` 分流：去掉外框、底色、竖旗，
  改为透明背景 + 一条 1px 基线（`::after`），像设备自检面板。
- 三个方块保持宿主尺寸，`gap: 8px → 5px` 收成一组指示灯；
  动画换成 `ef-load-step`：720ms、`steps(1, end)` 硬切三档（0.26 / 0.58 / 1），
  不弹跳、不缩放、不发光。
- 错峰用 `nth-child(2|3)` 补回 120ms / 240ms：宿主的让内联
  `animation-delay` 被 `.animate-bounce{animation:none!important}` 的**简写**清零了，
  所以新规则只写 `animation-name/duration/timing-function/iteration-count` 四个长属性，
  不用 `animation` 简写。
- 颜色：浅色用墨（10px 黄方块压白纸只有 1.1:1），深色才用强调色。
- `prefers-reduced-motion: reduce` 与 `motion=calm` 下停表，三点保持全亮。

### 验证

- pytest：**75 passed**（新增 1 条：外框摘除、steps 硬切、禁用简写、错峰延迟、双主题配色）。
- 真机 1440 深色/浅色各抓两帧：`animation-delay = 0 / 0.12 / 0.24s`，
  opacity 依次变化，确认在「一档一档亮」，不是同步闪。
- 门禁：**PASS 3 / SKIP 0 / FAIL 0**。

## 0.5.2 (2026-11-28)

深色模式下两处「主题强调色与宿主自带色叠加」的冲突。

### A. 配置页下拉：黄底上套黑块

- 配置页「选择设置页面」下拉的每行是 `.dashboard-button--outline`
  （`data-config-section-menu-row`），悬停时主题铺强调色；
  行内 Radix `menuitem` 又按自己的 focus 态铺了一层深底，
  叠加成「黄底 + 黑块 + 白字」。
- 改为：外层行承担底色，内层 `menuitem`（含 `data-highlighted`、
  `:focus-visible`）背景透明、颜色继承。
- 真机验证：悬停「记忆」行 `rowBg=rgb(255,250,0)`、`itemBg=rgba(0,0,0,0)`、
  文字 `rgb(22,22,22)`。

### B. 插件市场徽章：宿主橙色与单一强调色冲突

- 榜单徽章（`data-plugin-growth-badge`）与已安装徽章
  （`data-plugin-installed-badge`）由宿主写死 `bg-orange-700 / dark:bg-orange-400`。
- 改为：榜单走强调色填充 + 墨字，已安装走墨底反白，均为方形无投影。

### 验证

- pytest：**74 passed**（新增 2 条：下拉单层底色、徽章跟随单一强调色）。
- 反向验证：删掉 menuitem 透明规则 / 把徽章改回橙色，对应用例均失败。
- 门禁：**PASS 3 / SKIP 0 / FAIL 0**。

## 0.5.1 (2026-11-28)

在 MaiBot **1.4.8 / dashboard 1.10.8 / SDK 2.23.0** 的本地实例上装着实跑复核后的修正。
桌面深色与浅色结构成立；问题集中在一处门控缺陷和一列被放大的统计数字。

### A. 修复：注释紧邻 `@media` / `@container` 导致整块规则静默失效

- `et_stylegate.gate_css` 解析规则头时，把「前置注释 + `@media`」整段当成选择器，
  拼出 `html:not([data-dashboard-style='millennium'])… @media (max-width: 640px){…}`
  这种非法 CSS，浏览器整块丢弃。
- 全文件共 **6 处**受影响：触屏 `hover:none`、宽容器主读数、两种 `prefers-reduced-motion`、
  `max-width: 1023px` 移动端适配、`max-width: 640px` 窄屏适配。
  也就是说 0.5.0 及更早交付的「移动端适配 / 减少动效降级 / 触屏去悬停」**一直没有真正生效**。
- 修法：判断 at-rule 前先剥离前导注释，输出仍保留原注释（不影响可读性）。
- 反向验证：把 `head_code` 改回 `head.strip()`，新增用例立即失败。

### B. 统计页主读数不再被截断

- `[data-stats-kpis]` 是 `repeat(4, minmax(0,1fr))` 四列网格，宿主对
  `[data-stats-kpi] [data-board-number]` 写了 `overflow:hidden + text-overflow:ellipsis`。
- 0.5.0 把它放大到 `2.75rem` 后，真机上 `¥0.65` 显示成 `¥0....`、`58.76万` 显示成 `58....`。
- 改法：统计 KPI 回到宿主字号 `1.75rem` 并取消额外加宽（`font-stretch: 100%`）；
  放大只保留在观察首页，且限定在 `@container board (min-width: 56rem)` 宽容器内。

### C. 统计页小字键值行不再硬切

- `花费/消息数量` 曾被切成「花费/消」「总数量」两行，`50.13` 与「万」分行。
- 改为：标签过长收省略号（`text-overflow: ellipsis`），数值 `flex-shrink: 0` + `nowrap`。

### D. 窄屏（≤640px）收回装饰，把宽度让给内容

- 收起 `data-board-module-code` / `data-board-rule-code` 英文代号与资讯条 `//` 前缀，
  卡片标题只留中文。
- 主读数降到 `1.5rem`，`data-observation-hero` 与磁盘/资讯行回到 100% 字宽。
- **不改宿主布局**：原版 390px 同样把「活动」排两行、把磁盘数值省略，
  这是宿主既有表现，主题只负责别把字撑得更宽。

### E. 已知但未改（宿主结构 / 数据量所致）

- `// PERIOD`、`// CACHE`、`// MODELS` 在数据少时留白偏大；
  统计页 9 个「新增」增量标签偏吵；`// STATS` 与右侧时段切换器分居两端。
- 这些由宿主卡片高度与布局决定，强行改写会与宿主升级冲突，留给宿主。

### 验证

- pytest：**72 passed**（新增 4 条：门控注释回归、KPI 字号上限、键值行省略、窄屏收代号）。
- 反向验证 3/3：门控注释剥离、统计 KPI 字号、窄屏收代号，改回旧实现均失败，恢复后 SHA-256 一致。
- 门禁：**PASS 3 / SKIP 0 / FAIL 0**；静态检查 36 PASS / 1 预期 WARN；冒烟 OK。
- 真机复核：1440 浅色/深色、390 手机三种视口 `scrollWidth == clientWidth`，无横向溢出。

## 0.5.0 (2026-11-28)

全 WebUI 结构强化，并把新配置的默认强调色改为标准黄。方向经确认：
只加强结构、版式和真实数据层级，不靠提高荧光色或底纹浓度制造差异。

### A. 默认强调色改为标准黄

- `AppearanceConfig.accent` 默认 `lime → yellow`；`resolve()` 对非法 accent 也回退 `yellow`。
- 已有 `config.toml` 中显式保存的 accent 不被覆盖；旧实例仍显示原选择，
  README 增加对应排查项，避免把“配置优先”误判成升级失败。
- 显式选择青柠、冰蓝、琥珀仍可用，其余五个外观维度默认值不变。

### B. 全站页标题与结构基线

- 只在 `[data-dashboard-main]` 内接管标题：h1 增加 `//` 结构前缀和硬分段三色条
  （品红 / 当前强调色 / 薄荷），三色条只出现在页面开始处。
- 没有可靠英文字段时不伪造英文眉标；英文小字继续来自宿主真实
  `data-board-module-code` / `data-board-rule-code` 等字段。
- 排除宿主 404 的 `150px` 状态码（不加 `//`/三色条，也不改字号）和移动端
  `data-mobile-large-title` 的既有字号，避免通用规则压坏两个特殊情况。
- h2/h3 只统一字重、行高和字距；`time`、`[data-numeric]`、统计生成时间改用宽体等宽数字。

### C. 页框、数据屏与记录行

- `PageFrame` / `DataPanel` 统一 **1px** 细线（宿主 PageFrame 原为 2px），保持直角；
  只读面板不切角。
- `[data-dashboard-list-item]` 改成记录行：细线分隔，可点行右下小切角，
  右留白同时计入切角与 Prompt 目录的滚动条预留宽度；当前项强调色填充 + 墨字 + 粗体，
  不让“当前”只靠颜色表达。
- 统计明细按钮行纳入同一套记录行语法；桌面悬停右移 6px，减少动效时整段不生效。

### D. 可点大切角与主读数

- 插件市场 `PluginCard` 使用 `--ef-cut-panel` 大切角，仅命中真实整卡可点的
  `data-plugin-market-card`；底部 padding 与切角等高，`wide` 档也不会压到操作按钮。
- 观察首页 `data-observation-usage-big` 与统计页 `data-stats-kpi` 的真实主读数放大到
  `clamp(1.75rem, 1.35rem + 1.2vw, 2.75rem)`；普通正文和表格字号不变。
- 只读看板模块与卡片保持直角，形状语义不变。

### E. 选择器核对与测试基建

- 对照本机 MaiBot 1.4.8 / dashboard 1.10.8 源码确认：
  `[data-observation-page-bar]` 在该版本只有 CSS、没有真实 JSX 消费者，
  本次不作为结构强化支点，新规则落在真实存在的 `data-dashboard-main`、
  `data-dashboard-page-frame`、`data-dashboard-list-item`、`data-plugin-market-card`
  与统计/看板数据属性上。
- 修正旧测试的绝对导入 `import et_variants`：从工作区执行 pytest 时不稳定，
  改为与其它用例一致的包式 `import_module("endfield_theme.et_variants")`。

### 验证

- pytest：**69 passed**（新增 6 条：默认色 1 条 + 结构规则/门控 5 条；更新旧配置热更新断言）。
- 冒烟：**smoke: OK**（注入 → 幂等 → 热更新 → 停用移除 → 卸载还原）。
- 门禁：**PASS 3 / SKIP 0 / FAIL 0**；静态检查 36 PASS / 1 WARN / 0 FAIL
  （WARN = 纯注入插件无组件装饰器，属预期）。
- 反向验证 3 轮，均先确认对应用例失败，再按字节恢复文件：
  1. 删掉插件市场卡的底部切角留白 → 大切角用例 **1 failed**；
  2. 去掉当前记录行的粗体备份 → 记录行用例 **1 failed**；
  3. 默认 accent 改回 lime → 默认色用例 **1 failed**。
  每轮恢复后文件 SHA-256 与改动前一致。
- 视觉复核（**partial**）：用本机 dashboard 1.10.8 编译样式和宿主
  `observation/surfaces/board/statistics` 路由样式搭建隔离夹具，
  检查 1366×900 浅色/深色与 CDP 强制 390×844 手机视口。
  三档均为 `scrollWidth == clientWidth`（无横向溢出），未发现文字重叠、
  切角压字或主读数裁切；插件卡大切角内无控件。夹具不等于完整真机页面，
  登录态页面与真实数据密度仍需真机复核。

### 已知边界

- 已有配置的 accent 不会被改；默认值只影响新实例与非法值回退。
- 本仓库仍没有真实 dashboard 的截图基线；像素级观感需要在真机 WebUI 复核。

## 0.4.4 (2026-11-23)

按 endfield-ui skill 全量审计后的四项整治：无障碍焦点环、提示条竖旗可见性、
报错配色语义、深色装饰面对比度区间。前三项经用户逐项裁决后实施。

### A. 键盘焦点环补齐（无障碍，影响面最大）

- 根因：宿主 `index.css:7-17` 有一层
  `@layer dashboard-focus { :focus, :focus-visible { outline: none !important;
  --tw-ring-shadow: 0 0 #0000 !important } }`，**全局关掉焦点框**。
  本主题此前只给 `.dashboard-button` / `[data-observation-key]` /
  `[data-observation-period] > button` / `input,textarea` 四类补了焦点环。
- 但宿主里有 **205 处裸 `<button>`，带 `dashboard-button` 类的 0 处**
  （`routes/auth.tsx:365`、`chat/FileAttachment.tsx:23`、
  `ChatUserIdentity.tsx:55/89`、`LocalBotAvatarSettings.tsx:23` 等），
  加上 switch / checkbox / radio / tab / 链接，**键盘 Tab 过去完全没有焦点提示**。
  接管了「关焦点框」这件事却没补齐，等于把无障碍做坏了。
- 修复：新增第 2b 节兜底，覆盖
  `button / a / select / summary / input / textarea /
  [role=switch|checkbox|radio|tab|menuitem|option] / [tabindex]:not([tabindex='-1'])`
  的 `:focus-visible`，2px 实线 + `!important`，并一并压掉 `--tw-ring-shadow`。
  浅色墨 `--ef-ink`、深色 `--ef-accent`；命令栏恒深色故单独强制强调色。
- 层叠：本主题 CSS **不带 `@layer`**，无层声明优先级高于任何 `@layer`，
  因此 `!important` 能压过宿主那层。兜底块放在**所有专用焦点规则之前**，
  让按钮 `+2px` / 周期拨杆 `-2px` / 输入框 `-1px` 各自的 `outline-offset` 按顺序覆盖，
  既有观感不变。

### B. 提示条竖旗改墨（浅色下原本等于不存在）

- 根因：第 9 节 `border-left: 4px solid var(--ef-accent)` 落在
  `background: var(--ef-panel)`（浅色纯白）。这是**一条纯线，不是填充**——
  旁边没有同色底，可见性只能靠自身与纸的色差。实测四强调色 × 三纸色 12 组：
  yellow **1.11** / lime（默认）**1.21** / ice **1.44** / amber **1.79**，
  按「文字与线 ≥3:1」**全部不达标**。
- 对照：按钮 hover(`:224`)、radio(`:789`)、状态灯(`:808`)、选项指示器(`:965`)
  四处也用 accent 描边，但它们**同时声明 `background: var(--ef-accent)`**，
  边与填充同色属填充语义 ⇒ 合规，本次不动。
- 修复：浅色竖旗改 `--ef-ink`（压白板 18.1:1），深色新增 `html.dark` 分支用
  `--ef-accent`。与焦点环、状态灯「浅底用墨、深底用黄」的处理一致。
  黄色仍留在按钮 / 徽章 / 选中态等**填充**语义处。

### C. 报错提示条去掉红色（严格执行「红色只给删除」）

- 根因：旧版 `[role='status'].destructive, .toast.destructive` 保留红边，
  注释写「删除语义」。但宿主 `toast.tsx:40` 把**「删除失败」与「保存失败」
  「学习配置保存失败」等一律标成同一个 `.destructive` 类**，无额外 data 属性，
  **CSS 无法区分二者**。旧实现等于把红给了报错，违反 skill「红色只给删除」。
- 修复（用户裁决：报错一律去红）：删除该规则，所有提示条统一走 B 的墨/黄竖旗，
  错误由标题文字「XX失败」表达，不靠颜色。
- 红色保留给真正的删除控件：`.dashboard-button--destructive`(`:288`)、
  `[data-observation-card-remove]`(`:609`)。全文件 `--ef-danger` 消费者已复核为这 2 处。
- 已知代价：删除失败的提示也不再是红的，扫视时无法靠颜色区分成功/失败。

### D. 深色等高线降到 16%（落进装饰面对比度区间）

- skill `verification.md` 装饰面区间 **1.06–1.60**（有下限也有上限）。
  `--ef-contour` 此前两模式共用 `ink 18%`（0.2.0 按用户「再明显一点」从 9% 提上来）。
  浅色实测 1.453–1.469 ✅；**深色 1.670–1.712，六组合全部超上限**。
  原因：浅墨 `#EDEDED` 在深底上比墨在浅底上更「跳」，同 alpha 不等效。
- 修复：`dark_own` 新增 `--ef-contour: ink 16%`，实测 **1.570–1.590**，
  三纸色 × paper/panel 六组合全部落区间，且是合规范围内**最浓一档**，
  保留用户要的「明显」。浅色保持 18% 不变。
- 全量复核：三纸色 × 深浅 × paper/panel = **12 组，超区间 0**。

### 验证

- 用例 56 → **63**（新增 7 条）：焦点兜底覆盖面 / 深色与命令栏用强调色 /
  兜底先于专用规则（层叠顺序）/ 竖旗双模式 ≥3 含 12 组反面对照 /
  报错无红且红色只在删除选择器 / 装饰面 12 组落区间含深色 18% 反面对照 /
  新规则门控后逐分支带让位前缀。
- **三轮反向验证**（改回旧实现 → 确认对应用例 FAIL → 从备份恢复 → 全绿）：
  1. 整块移除焦点兜底 → **4 红**（三条焦点用例 + 门控用例）
  2. 竖旗退回 accent + 加回 destructive 红边 → **3 红**
  3. 移除深色 contour 覆盖（退回共用 18%）→ **1 红**
  每轮恢复后 63 passed，且 `diff` 确认与备份逐字节一致。
- 门禁 `gate.sh`：**PASS 3 / SKIP 0 / FAIL 0**；check_plugin 35 PASS / 1 WARN / 0 FAIL
  （WARN =「未发现任何组件装饰器」，纯注入式主题插件本就没有组件，属预期）。

### 本次审计已验证合规、未改动的项

reduced-motion 门控 0 条漏网（3 个 `infinite` 全在 `no-preference` 块内，
18 条 `!important` 动画逐条核验）；致产属性 `will-change`/`filter`/`container-type`/
`contain`/`perspective` 零命中；圆角零残留、阴影仅 1 处硬边 `inset 0 0 0 1px`；
切角压字逐尺寸算过 12 组全安全；墨字压四 accent 10.10–16.31 均 ≥7；
宿主 CSS 零处把 chart 色写成 `color:`；`--list-selected-*`/`--chat-outgoing-*` 成对接管；
`:713` 头像描边已核实在恒深色命令栏内（`ObservationSidebar.tsx:553`）；
字体许可 `fonts/Saira-OFL.txt` 已随附。

### 已知缺口（本次未做，待裁决）

- `endfield-fx.js` 保存反馈只认中文（`/保存/`、`indexOf('配置已保存')`），
  宿主为四语（en `Plugin configuration saved` / ja `保存しました` / ko `저장됨`），
  非中文界面下黄穿按钮 / 「已保存」替换 / 删行 FLIP 全部不触发。
  同文件深浅揭幕那段反而做了四语正则，说明是遗漏而非设计。
- `html { font-stretch: 112%; font-variant-numeric: tabular-nums }` 全局字体声明
  会泄漏到宿主嵌入的第三方内容（属行为变更，已向用户解释，等授权）。
- `--ef-cut-panel`（26px 基准）定义了但消费者 0 处，死代码。

## 0.4.3 (2026-11-22)

加载动效整治：修掉 0.4.2 遗留的**功能性回归**（加载指示几乎不可见），并按 skill 补齐机械加载语法。

- 根因：0.2.0 起第 14 节是一条无差别的
  `.animate-pulse { animation: none; background: 45°斜线纹(6.5px 周期) }`。
  但 dashboard 把 `animate-pulse` 用在**四种完全不同的东西**上，一条规则全铺纹：
  - **6px 状态小点**（`MessageList.tsx:137-151` 聊天「正在思考」三点 `h-1.5 w-1.5`
    `bg-primary/70|60|50`；`AgentWorkspace.tsx:162` 运行点 `size-1.5 bg-primary`）：
    6×6 里 45° 斜纹按几何积分只覆盖 **21.5%** 面积，纹线本身又只有 `ink 22%`，
    合成后浅色 **1.10:1** / 深色 **1.14:1**（原生分别是 6.69 / 7.66），
    远低于图形门槛 3:1 —— 等于**加载指示消失**。这是本次最严重的问题。
  - **14px SVG 图标**（`prompts.tsx:1074/1141` `CheckCircle2` / `GitCompareArrows`
    `size-3.5 + animate-pulse`）：图标底下被铺一层与它无关的斜纹。
  - **有完整内容的状态卡**（`providerStatus.tsx:10`、`ModelTable.tsx:80`、
    `ModelCardList.tsx:42`，均为 `border-amber-500 animate-pulse`）：整张卡文字被纹压住。
  - **真空骨架**（`skeleton.tsx:9` `bg-primary/10`、`CodeEditor.tsx:42`、
    `context-items.tsx:290`）：只有这一类该铺纹。
  skill `motion.md` 原文是「正在处理 → **按钮**铺斜线纹、暂停响应，不放转圈」，
  说的是按钮 busy 态，不是「所有 pulse 元素」——属实现偏离规范。
- 修复 A（按角色分流，第 14 节）：裸 `.animate-pulse` 只停原生脉冲、不再声明 background；
  斜线纹收窄到 `.bg-primary\/10` / `.bg-muted` / `.bg-muted\/20` 三个空占位特征；
  状态小点改**实心墨/黄方块 + `ef-dot-step` 步进硬亮**（900ms，`steps(1,end)`，
  复用原生 `animation-delay:150/300ms` 错峰，不改 DOM、不引入 JS）；
  SVG 图标 busy 不铺纹；状态卡改**左侧 3px 竖条**（浅墨/深黄）+ 细线边框，内容不受干扰。
  另把 `MessageList.tsx:84` 的装饰发光光晕（`blur-xl` + `-z-10`）直接 `display:none`（语法无发光）。
- 修复 B（第 11 节，此前完全漏网）：`.animate-spin.border-primary` **只命中 setup 页 1 处**
  border 环；全站数十处是 `<Loader2 className="animate-spin"/>` / `RefreshCw` / `RotateCcw`
  的 **SVG**，不带 `border-primary`，一个也没被接管。现统一给 `svg.animate-spin`
  明确颜色（浅墨 18.10:1 / 深黄 14.34:1），并把原生 linear 匀速旋转换成
  `ef-spin-step` **8 格跳格**（`steps(8,end)`，800ms），符合「短硬机械」。
- 修复 C（重启遮罩）：`restart-overlay.tsx:88/94/100` 的 `h-16 w-16` 大转圈是整屏最抢眼元素，
  按 skill「不放转圈」改成**一段黄格横走**（`ef-indeterminate-bg` 1200ms linear，
  保留原 64×64 占位不动布局，双层 background 画「轨 + 格」，图标线条置 transparent）。
  `animate-ping` 扩散圈与 `animate-bounce` 粒子继续静止。
- 修复 D（分段进度条）：用官方稳定钩子 `data-dashboard-progress` / `-indicator`
  （`progress.tsx:15/22`，非哈希类名），轨道画 **24 格**分隔线（`::after` 覆盖层压在黄格之上，
  `pointer-events:none`），Indicator 的 `translateX` 过渡改 `steps(24,end)` **按格跳**；
  `value=null`（无 `translateX`）时识别为不知进度，黄格收窄到 25%。
- 减少动效：全部新动画包在 `@media (prefers-reduced-motion: no-preference)` 内。
  该设置下小点保持 `opacity:1` 常亮、黄格静止在最左 —— **状态不丢**（旁边有文案与百分比）。
- 测试：47 → 56（+9：裸 pulse 不再铺纹、骨架限定特征、小点实心+步进+光晕关闭、
  SVG 转圈接管、状态卡与图标不铺纹、重启大指示改黄格、进度条 24 格 steps、
  加载态双模式 WCAG 复算并附「斜纹小点 1.10:1」反面对照、门控后逐分支带让位前缀）。
  **反向验证三轮**：退回无差别铺纹 → 1 红；移除 SVG 转圈接管与重启黄格 → 2 红；
  进度条退回平滑滑动 + 状态卡退回铺纹 → 2 红。每轮均从备份恢复后复跑 56 全绿。
- 门禁：PASS 3 / SKIP 0 / FAIL 0（静态 35 PASS / 1 WARN 预期）。

## 0.4.2 (2026-11-22)

热修真机反馈「浅色模式下黄色字体看不清」（麦麦观察首页 Token 消耗柱图提示框）。

- 根因：recharts `DefaultTooltipContent` 把每个系列的颜色写成 `<li>` / `<span>` 的
  **行内 `color`**（`color: entry.color`，而 `entry.color = Bar 的 fill`）。
  行内样式压过本主题给 `.recharts-default-tooltip` 容器设的 `color`，
  于是浅色下「输入」行是 `#FFFA00` 压白板 `#FFFFFF` = **1.11:1**（完全看不见）；
  「输出」行是 `--board-chart-2`（墨 45%）合成 `#969696` = **2.95:1**，同样不达 AA。
  深色下「输入」14.34:1 正常，「输出」3.88:1 也偏低——所以这不是纯浅色问题。
- 修复（CSS 第 8 节）：图表色是**填充语义**，不得当文字色。
  - `.recharts-tooltip-item` / `-name` / `-separator` / `-value` / `-unit` /
    `.recharts-tooltip-label` / `.recharts-legend-item-text` 一律 `color: var(--ef-ink)`；
  - 名称与图例文字用次要墨 `--ef-ink2`（浅 6.69:1 / 深 6.31:1）；
  - 标签加粗、数值 `tabular-nums`、名称与数值之间补 0.5rem 间距
    （原生两者紧贴，`modern.css` 只给自定义 tooltip 补过）。
  - 图例文字同类缺陷一并修（`DefaultLegendContent` 也写行内 `color`）。
- 顺藤摸出的同类：成功图标 `.text-green-500`（重启遮罩 / 表情审核「全部审核完成」/
  插件统计点赞）此前统一改强调色，但它们落在**浅底**上（白板、`bg-muted/50` 浅圆底），
  黄图标压白板 1.11:1 < 3:1 图标门槛 → 改为浅色用墨、深色才用强调色。
- 测试：43 → 47（+4：tooltip 文字不沿用系列色、修复后双模式 WCAG 复算并附修复前反面对照、
  成功图标浅色用墨、门控后 7 条选择器分支全部带让位前缀）。
  反向验证两轮：移除 tooltip 覆盖 → 2 红；成功图标退回纯强调色 → 1 红。
- 门禁：PASS 3 / SKIP 0 / FAIL 0（静态 35 PASS / 1 WARN 预期）。

## 0.4.1 (2026-11-22)

热修真机反馈「浅色时左侧变化不完全」：浅色模式侧栏会话名称整片消失。

- 根因：原生 `conversation.css` 给会话条目设 `color: var(--surface-ink)`，
  本主题 preamble 把 `--surface-ink` 压成 `--ef-ink`（浅色=墨），而侧栏恒深色
  命令栏 → 浅色模式墨字墨底，名称不可读（深色 `--surface-ink`=浅字所以正常）。
  预览「空闲」走 status 的 muted-foreground 灰，两种模式都可见，故只有名称消失。
- 修复（CSS 4f 节）：
  - 会话条目强制 `color:#EDEDED`（不跟 `--surface-ink` 走），分隔线改 `#353535`；
  - 名称 strong 继承条目浅字；非选中预览/状态用命令栏灰 `#A3A3A3`；
  - 选中态预览/状态转墨色半透明 `rgba(22,22,22,.72)`（强调色底上可读）；
  - 悬停改命令栏深灰 `#2E2E2E`（原生 `--list-hover-bg` 浅色是浅灰会翻车）。
- 折叠态（图标轨）一并修：
  - 选中/悬停条目原生 `color:var(--surface-ink)` → 强制浅字、背景透明；
  - 堆叠头像分隔边原生 `hsl(var(--background))`（浅色=白）→ 改命令栏底色。
- 测试：41 → 43（+2：浅色侧栏会话可读性反向验证、注入产物条目颜色不依赖 surface-ink）。
- 门禁：PASS 3 / SKIP 0 / FAIL 0。

## 0.4.0 (2026-11-22)

对照 endfield-ui skill 补齐三类缺口（grill 决策落定）：官方风格让位、
六维变体补全、操作反馈 JS 层。默认值 = 0.3.0 现状，升级零外观变化。

- **官方风格让位**（新增 et_stylegate.py）：
  - WebUI 界面风格选「千禧」/「未来复古」时主题 100% 失效，界面回官方原样；
    切回「现代」即时恢复，无需重启。
  - 实现：纯 CSS 选择器门控——每条规则加
    `html:not([data-dashboard-style='millennium']):not([data-dashboard-style='future-retro'])`，
    不摘注入。preamble 变量块同样门控（让位时行内 token 不再被压）。
  - 手写 CSS 扫描器：条件 at-rule 递归、keyframes/font-face 跳过、
    逗号列表逐段门控；212 条规则头全门控、232 个声明体逐字节不变（测试断言）。
- **六维变体**（et_variants.py / et_config.py）：
  - 新增 cut（tight ×0.6 / standard ×1 / wide ×1.6）：切角变量全部改缩放，
    硬编码 5px/4px 换 `--ef-cut-badge`/`--ef-cut-action`。
  - 新增 ground（contours/grid/hatch/plain）：grid=1px 网格 3rem + 径向 mask，
    hatch=`--ef-hatch` 斜线纹 + 双 linear-gradient mask，plain=隐藏底纹。
  - 新增 motion（full/calm）：calm 压掉入场动画（对话框/浮层/提示条/标签页 open），
    保留退出与回应（hover/按下/切换）。
  - ground/motion 经 `variant_attrs()` 写到 `<html>` 属性，CSS 按属性选择器消费；
    卸载/停用逐个摘除。
  - 配置页三新开关中文化齐全（label/hint/choice 双语）。
- **操作反馈 JS 层**（新增 theme/endfield-fx.js，约 9KB）：
  - flashDone：保存成功（「配置已保存」toast）→ 黄色穿按钮一次 600ms mech +
    标签「保存」临时变「已保存」1200ms（只动文本节点，不碰 React 结构）。
  - 删行补位：pointerdown/keydown 冻结兄弟行几何 → React 移除 TR 后
    FLIP translateY 200ms snap（MutationObserver 回调时布局已重算，
    几何必须提前冻结——这是关键设计点）。
  - toast 卸载兜底：Radix 受控 toast 直接卸载时克隆一份补完 160ms 擦出
    （aria-hidden + data-ef-ghost，不进读屏、不被二次识别）。
  - 深浅揭幕：统一接管三个入口（侧边栏按钮/外观页分段控件/auth 页按钮），
    click 捕获拦截 → startViewTransition 圆形揭幕 420ms MECH。
    官方侧边栏自带 500ms ease-in-out 软曲线被替代（WAAPI 优先级高于 CSS，
    无法只压曲线）；四语 aria-label 匹配（zh/en/ja/ko）。
  - 静止条件：prefers-reduced-motion / motion=calm / 千禧/复古让位 /
    no-animations / Edge / 无 View Transitions API，任一满足即全部不动。
  - 砍掉展示页语法：乱码落定/指针视差/分段圆盘不进后台。
  - CSS 配套（第 17 节）：ef-done 关键帧 + ef-is-done 黄穿 + ef-out-wipe +
    view-transition 层抑制（旧层不淡出、新层不做默认动画）。
- **plugin.py 注入闭环扩展**：
  - 新增 `<script id="endfield-theme-fx" defer src="/fonts/endfield/endfield-fx.js">`
    注入与正则清理；fx.js 随字体资产分发进 dist，卸载一并清理。
  - `<html>` 变体属性注入/摘除（限定 html 标签范围，不误伤 body 内同名属性）。
  - `_build_style` 接入 gate_preamble + gate_css；日志行带六维。
- 测试：26 → 41 用例（+15：六维默认/缩放/回退/属性、ground 四态、calm 语义、
  配置页六开关、门控无漏网/声明体不变/preamble、JS 存在/语法/注入-移除闭环、
  html 属性生命周期、CSS 反馈配套、默认外观零变化）。
- 门禁：PASS 3 / SKIP 0 / FAIL 0（静态 35 PASS 1 WARN 预期）。

## 0.3.0 (2026-11-22)

补齐「麦麦观察」首页覆盖（用户反馈「左侧的麦麦观察页没动」）。
根因：首页（ObservationHome）走独立的 `--board-*` 看板层 + `--surface-*`/`--list-*`
表面层 + 大量 `data-observation-*`/`data-board-*` 专属部件，此前主题只覆盖了
`--color-*` 与侧栏 `--obs-side/key-*`，首页整片保持官方外观。

- 变量层补齐（et_variants.py，全部 !important 压行内 token）：
  - `--board-*` 14 项：module/screen 直角零阴影、细线边框、墨色文字、
    Saira 数字/代号字体；`--board-chart-1`=强调色、chart-2=墨 45%、
    网格/轴线=细线色（图表不用红绿，随深浅两套）。
  - `--surface-*`/`--list-*` 12 项：页面框/数据屏直角零阴影零纹理、
    列表选中=强调色底+墨字、hover=浅灰。
  - `--chat-*` 6 项：气泡直角零阴影、发出=强调色底+墨字。
  - `--obs-heading-font`/`--obs-plate-font`=Saira、`--obs-edit` 浅色墨/深色强调色。
- CSS 新增五节（4b–4f，约 17KB）：
  - 4b 看板层：模块直角细线 + 顶边粗墨页签（14% → hover/focus 整条伸开，
    400ms mech）；英文代号 `display:inline` + `// ` 前缀 + 125% 宽体
    （原生 millennium/future-retro 才显示，现三风格统一显示）；
    数字 Saira 等宽；徽章方形强调色切角。
  - 4c 首页部件：hero 运行=强调色/停止=墨（去红）；key-badge/news 未读点/
    model-dot 方形；周期拨杆方形凹槽 + 墨底反白滑块 280ms mech；
    卡片操作切角 hover 强调色；编辑虚线/拖拽 45° 斜线纹；卡片库直角细线。
  - 4d 底部输入条：直角细线去双层投影；ask 模式灯与发送键由原生
    `hsl(152 55% …)` 绿改强调色+墨字；mode-tail 去 inset 白高光改细线。
  - 4e 桌宠卡片：气泡直角浅灰底、thinking 改斜线纹、footer 实线、
    todo-badge 方形强调色。
  - 4f 侧栏会话：选中=强调色底+墨字；头像直角、非 bot 统一浅灰+墨
    （消除六种彩色 tone）、bot=强调色；图标轨 `#22c55e` 绿描边改强调色；
    会话计数方形；modern 侧栏白卡改深色命令栏配套。
- 失效选择器修正（对照 dashboard 1.10.8 源码逐一核实）：
  - `data-sonner-toast` → `data-dashboard-toast`（真机无 sonner 属性）
  - `data-radix-slider-*` → `data-dashboard-slider-*`
  - `data-mobile-tab-bar` → `data-mobile-tabbar`（无连字符 tab-bar）
  - `[data-slot='card']`/`'input'`（不存在）→ `data-dashboard-card`/`-input`
  - `data-radix-select-trigger` → `data-dashboard-select-trigger`
- 其余违规点一并压掉：
  - modern 磨砂玻璃浮层/弹窗/图表提示框/卡片：去 backdrop-filter 与玻璃投影，
    实底细线；对话框遮罩改墨色 62%。
  - modern 设置页签 primary 下划线 → 墨底反白；分段选择凹槽圆角+inset 投影 →
    方形细线；管理页当前导航项透明底+2px 左线 → 强调色整块+切角。
  - 单选圆点 50% 圆形 → 方形；选项卡指示器空心圆 → 方形。
  - 移动端 `.m-glass` 玻璃 + 按压缩放弹跳 → 实底细线静止；
    功能状态灯被 modern 改回的绿圆点（--m-ok）→ 方形强调色。
  - 重启遮罩 ping 扩散圈/bounce 粒子循环装饰动画 → 静止（进度条/转圈保留）；
    成功图标 text-green-500 绿 → 强调色。
- 实测：门禁 PASS 3 / SKIP 0 / FAIL 0；pytest 26 passed（新增首页覆盖
  反向验证 4 例）；冒烟全过。版本锚点同步 0.3.0。

## 0.2.1 (2026-11-22)

修复：浅色模式强调色文字不可读（用户真机截图：「运行中 1」「当前 Bot 玲澜」
「GATEWAY 路径」呈黄字，白底对比度约 1.1:1，违反 skill「浅色主题黄色不能当线或字」）。

- 根因：preamble 把 --color-primary 设成强调色，dashboard 大量用 text-primary
  渲染文字/图标（HostDashboard 计数与 Bot 名、GATEWAY 路径、配置节标题等）。
- 修复：primary 语义改为「可读品牌色」——浅色=墨色、深色=强调色（深底上可读）；
  「选中/当前=强调色填充」的部件在 CSS 显式用 --ef-accent，不再依赖 primary token：
  - .bg-primary.text-primary-foreground（选中徽章/按钮/多选标签）→ 强调色底+墨字
  - 开关/复选框/单选选中态、进度条/滑条填充（原有规则保留）
  - 功能状态灯 enabled → 强调色（原生 hsl(--primary) 浅色下会变墨）
- 顺带纠正状态色语法（截图里可见的绿/红）：
  - 分段比例条：emerald→强调色、amber→斜线纹、destructive→墨、空闲→浅灰
  - 状态灯：方形无辉光；运行=强调色、处理中/异常=墨（红只给删除）、关闭=浅灰
  - 统计页 --stats-alert 由 destructive 红改墨
  - 加载转圈 border-primary：浅色墨/深色强调色
- 实测：门禁 PASS 3 / SKIP 0 / FAIL 0；pytest 22 passed（新增浅色 primary=墨
  四色遍历 + 强调色填充/状态色反向验证 2 例）；冒烟全过。
- 版本锚点同步 0.2.1；新增浅色预览页（复现截图场景）+ 深色预览同步重建。

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
