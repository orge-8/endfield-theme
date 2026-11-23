# 插件自定义 WebUI 页面适配终末地主题

面向 **MaiBot 插件开发者**。你的插件有 `webui.json` 里 `mode: "custom"` 的页面时，
按本文做，页面就能跟着 endfield-theme（以及任何官方风格）变色变形。

本文所有机制均以 **MaiBot 1.4.8 / dashboard 源码**核对，行号可复查。
文末用 `char-recog` 与 `cv_lyric_context` 两个真实插件做对照样例。

---

## 0. 先理解一件事：你的页面在沙箱里

自定义页面**不是**直接插进 dashboard 的 DOM，而是跑在：

```
<iframe sandbox="allow-scripts allow-forms" srcDoc={...}>
```

出处 `dashboard/src/components/plugin-custom-page.tsx:474-480`。

**没有 `allow-same-origin`** ⇒ iframe 内是 opaque origin ⇒
**读不到父页面任何东西**：拿不到 `html.dark`、拿不到主题注入的 `<style>`、
拿不到 `--ef-*` 变量、`localStorage` 也是隔离的。

CSP 更严（`lib/plugin-custom-page.ts:54-57`）：

```
default-src 'none'; script-src 'unsafe-inline' blob:; style-src 'unsafe-inline';
img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; ...
```

实际影响：

| 你想做的事 | 能不能 |
|---|---|
| 内联 `<style>` / `<script>` | ✅ 能（`unsafe-inline`） |
| `<link href="xxx.css">` 引外部样式 | ❌ **不能**（`default-src 'none'`） |
| `fetch()` 拿任何东西 | ❌ **不能**（`connect-src 'none'`） |
| `<img src="https://...">` | ❌ 不能，只能 `data:` / `blob:` |
| `@font-face src: url(https://...)` | ❌ 不能，只能 `data:` |
| 读父页面 DOM / 主题变量 | ❌ 不能 |

**所以「发一份 CSS 让开发者引 URL」这条路是走不通的，只能内联。**

### 宿主唯一的桥：探针采样

`lib/plugin-page-theme.ts` 在父页面放 8 个隐藏探针（真实 Button / Card / Input / span），
`getComputedStyle` 采样后拼成 CSS 送进 iframe。

**只传这 11 个外观属性**（`plugin-page-theme.ts:2-14`）：

```
background-color  background-image  background-size  color
border  border-radius  box-shadow
font-family  font-weight  font-size  line-height
```

由此得到 **13 个令牌**（`:95-115`）：

| 令牌 | 采样来源 |
|---|---|
| `--maibot-background` | 背景探针 `bg-background` |
| `--maibot-surface` | Card 背景 |
| `--maibot-foreground` | Card 文字 |
| `--maibot-muted` | `text-muted-foreground` |
| `--maibot-soft` | Input 背景（透明则回退 `bg-muted`） |
| `--maibot-border` | Card 上边框色 |
| `--maibot-primary` | Primary 按钮背景 |
| `--maibot-primary-foreground` | Primary 按钮文字 |
| `--maibot-danger` | Danger 按钮背景 |
| `--maibot-radius` | Card 圆角 |
| `--maibot-font-body` | Card 字体族 |
| `--maibot-font-display` | 风格标题字体（回退 Card 字体） |
| `--maibot-font-mono` | `--typography-font-family-code` |

外加 **5 组组件类规则**（`:120-130`）：`.maibot-button`（含 primary / danger / `[aria-pressed=true]`）、
`.maibot-card`、`.maibot-input` / `.maibot-select` / `.maibot-inset`，
以及页面基类 `.maibot-page`。

### 什么传得进、什么传不进

| 主题特征 | 自动传入 | 说明 |
|---|---|---|
| 配色（纸 / 墨 / 强调色 / 危险色） | ✅ | 走令牌 |
| **圆角归零** | ✅ | `border-radius` 在白名单里 |
| **柔和阴影归零** | ✅ | `box-shadow` 在白名单里 |
| 字体族名 | ⚠️ | 名字传得进，**字体文件传不进**（见下） |
| **切角 `clip-path`** | ❌ | 不在 11 项里 |
| `//` 眉标、等高线底纹 | ❌ | 伪元素 / 背景图，采样不到 |
| 机械动效、保存黄穿反馈 | ❌ | 依赖父页 DOM 观察，跨沙箱做不到 |
| 焦点环 | ❌ | **宿主主动关掉**，插件侧不要写，见第 3 节 |

**字体特例**：`pluginPageFonts()`（`plugin-page-theme.ts:28-37`）只白名单 4 个宿主字体
（Departure Mono / Ark Pixel 12px SC / Jersey 20 / JetBrains Mono），
按 `snapshot.styles` 里出现的族名去 fetch 并转 `data:` 注入。
主题的 **Saira 不在这个白名单里** ⇒ iframe 内 `font-family: "Saira"` 会**回退到系统字体**。
这是已知限制，不是你写错了。想要宽体观感，用 `letter-spacing` + `text-transform` 补，
别指望字体文件能进来。

---

## 1. A 层：正确消费令牌，配色与直角自动跟随

**这一层不需要装 endfield-theme 也该做**，做了就同时适配官方三风格。

> **⚠ 先分清两条路线（1.1 / 1.2 只适用于路线一）**
>
> | | 路线一：全面接受宿主观感 | 路线二：只跟形状，保住原样 |
> |---|---|---|
> | 做法 | 用 `maibot-page` + 宿主组件类（1.1 / 1.2） | 只用令牌（1.3）+ 第 2 节探测门控 |
> | 未装主题时 | 外观**由宿主决定**（padding / 字体被组件类接管） | 外观**与改造前逐像素一致** |
> | 适合 | 新页面，或愿意把观感交给宿主 | 已有一套自洽视觉的成熟页面 |
>
> **关键事实**：宿主组件类是**无条件注入**的（`plugin-page-theme.ts:120-130`，
> 与风格、与是否装主题都无关），且 `:133`/`:137` 写死了 padding。
> 所以「加组件类」和「没装主题时外观不变」**不可能同时成立**。
> 选路线二就**别加组件类**，实例见第 6.2 节（cv_lyric_context 2.23.0）。
>
> 1.3 起的各条（令牌回退值、圆角钳位、深色、CSP）**两条路线都必做**。

### 1.1 页面根用 `maibot-page`（路线一）

```html
<body class="maibot-page">
```

它负责把背景 / 文字 / 字体设成当前主题值（`plugin-page-theme.ts:132`）。
**如果你没有任何自己的底色声明**，不写这个类时深色主题下页面底色会是 iframe 默认白
⇒ 白底浅字，直接翻车。

路线二的等价做法：自己在根容器上写
`background: var(--maibot-background, 回退值); color: var(--maibot-foreground, 回退值)`
（cv_lyric 的 `.cvl-root` 就是这么做的，所以它不加 `maibot-page` 也不会翻车）。
**要点是「底色和文字色必须来自令牌」，不是「必须有那个类」。**

### 1.2 控件用宿主组件类（路线一）

```html
<button class="maibot-button maibot-button-primary">开始训练</button>
<button class="maibot-button">导出</button>
<span class="maibot-badge">v3</span>
<div class="maibot-card">…</div>
<input class="maibot-input">
<select class="maibot-select">…</select>
<table class="maibot-table">…</table>
```

宿主采样真实组件的 11 项属性写进这些类 ⇒ **配色、圆角、边框、字体一并跟随**。
自己写裸 `<button>` 不加类，就只能靠令牌手动上色，形状要自己补。

⚠ **代价**：这些类同时带宿主写死的 `padding`（`:133` 按钮 `8px 16px`、`:137` 卡片 `20px`），
而且**没装主题时也生效**。如果你的按钮/卡片已有自己的内边距，加类会把它改掉。
不接受这个代价就走路线二（第 2 节门控），别加类。

### 1.3 自定义颜色一律走令牌，并给回退值

```css
:root {
  --my-bg:   var(--maibot-background, #f7f8f6);
  --my-ink:  var(--maibot-foreground, #17181a);
  --my-dim:  var(--maibot-muted, #6c6f74);
  --my-line: var(--maibot-border, #e3e4e2);
  --my-hi:   var(--maibot-primary, #3a6ea5);
  --my-round: var(--maibot-radius, 12px);
}
```

回退值是必须的：SDK 送 context 之前有一小段时间令牌为空。

**禁止**：写死十六进制当主色。写死了主题就管不到那一块。

### 1.4 ⚠ 圆角不要用 `calc(令牌 - Npx)`

这是最容易踩的坑。主题把 `--maibot-radius` 变成 `0px`，于是：

```css
border-radius: calc(var(--maibot-radius) - 4px);   /* ⇒ -4px */
```

负圆角是**非法值，整条声明被丢弃**。

⚠ **这里有个反直觉的细节，别搞错**：`border-radius` **不继承**，声明被丢弃后元素取的是
该属性的**初始值 `0`**，不是「它自己的默认圆角」。所以在本主题下（令牌已经是 0）
它**碰巧仍然是方角**——是**隐患，不是现症**。真正会出问题的是令牌为某个小正值时
（例如官方风格把 `--visual-radius-lg` 调成 `2px`），`2px - 4px = -2px` 同样非法，
你想要的层级差就静默消失了。

不管哪种情况都该钳住，因为「靠非法值恰好得到想要的结果」不是设计：

```css
border-radius: var(--maibot-radius);          /* 直接用 */
/* 想要层级差就把下界夹在 0 */
border-radius: max(0px, calc(var(--maibot-radius) - 4px));
```

实际数量（2026-11-23 复核）：`cv_lyric_context` 曾有 **7 处**（不是早期文档写的 4 处），
`char-recog` 有 **1 处**（`.capture-thumb img`）。cv_lyric 的 7 处已在 2.23.0 全部钳住；
char-recog 那 1 处仍在，因主题下属上述「隐患非现症」情形，未列入该轮改动范围。

### 1.5 ⚠ 装饰性圆角要自己收

`border-radius: 999px`（胶囊）、`50%`（圆点）、`11px`（写死）这些**主题管不到**。
主题语法是「圆角全零」，所以要么改成走令牌，要么在 B 层门控里压平。

例外：**真正的圆点**（状态灯、进度点）保留 `50%` 是合理的——
主题本体也保留圆形状态点。判断标准是「它是不是一个点」，不是「它圆不圆」。

### 1.6 深色不要自己猜

SDK 会把深浅同步成 iframe 内的 `html.dark`（`lib/plugin-custom-page.ts:73`）。
写 `html.dark { … }` 即可，**不要**去读 `prefers-color-scheme`——
用户在 dashboard 里手动选的深浅与系统设置可能不一致。

---

## 2. B 层（可选）：切角与眉标，条件生效

想要「终末地味」而不只是「跟着变色」，才做这一层。

### 2.1 为什么必须条件生效

切角这类特征宿主传不进来，只能你自己写 CSS。但**你写的 CSS 在没装主题时也会生效** ⇒
没装主题的用户会看到「官方蓝 + 切角」的四不像。

所以要探测。**但宿主不传「装了哪个主题」**，只传 `theme`(light/dark) 与
`dashboardStyle`(modern/millennium/future-retro)——装了 endfield-theme 时
`dashboardStyle` 仍然是 `modern`。

⇒ **只能做能力探测（界面长什么样），不能做品牌探测（是谁装的）。**

### 2.2 判据（已实测，别自己改）

两条**都**命中才算：

1. **`--maibot-radius` 计算值为 0**
   主题覆盖 `--visual-radius-lg: 0px` ⇒ Card 探针圆角归零。
   官方 modern 是 `0.5rem`；千禧 / 未来复古**不覆盖这个变量**，
   且千禧给 `[data-dashboard-card]` 只改背景 / 边框 / 阴影、**不动圆角**
   （`styles/millennium.css:228-235`）⇒ 不会误判官方风格。

2. **`--maibot-font-body` 含宽体拉丁族名**（Saira / Bahnschrift）
   主题把 `--typography-font-family-base` 改成 `"Saira",…`，经 `--font-sans` 传到 Card。
   千禧用像素字体（Jersey 20 / Departure Mono / Ark Pixel）⇒ 不在此列。

**⚠ 不要用「强调色是荧光色」当判据。** 我一开始就是这么想的，实测被证伪：
主题**浅色下 `--color-primary` 是墨色**（`0.0 0.0% 8.6%`），只有深色才是荧光
（`82.3 100% 62%`）。用饱和度判会在浅色下 **24 个组合全部漏判**。

实测结果（四强调色 × 三纸色 × 深浅 = 24 组合）：

| 场景 | 期望 | 实测 |
|---|---|---|
| 主题在，24 组合 | 全部命中 | **漏判 0** |
| 官方 modern | 排除 | ✅ |
| 官方 millennium | 排除 | ✅ |
| 官方 future-retro | 排除 | ✅ |

宁可漏判不可误判：漏判只是少了切角（配色仍自动跟随），误判会污染没装主题的用户。

### 2.3 探测代码

见 `examples/endfield-page-adapter.js`（完整版含注释）或 `examples/example.html`（内联版）。

要点：

```js
// 主题样式不在初始 srcDoc 里，是 SDK ready 后 postMessage 送的
// ⇒ 必须监听事件，否则首次判定拿到空令牌
window.addEventListener('maibot:context', apply);
if (window.maibot?.context?.styles) apply();          // 事件早于脚本时的兜底
document.fonts?.ready.then(apply);                     // 字体异步加载后再判一次
```

命中就给 `<html>` 挂 `data-ef-page="on"`，你的 CSS 全部用它门控：

```css
html[data-ef-page='on'] .maibot-button {
  clip-path: polygon(0 0, 100% 0, 100% calc(100% - 6px), calc(100% - 6px) 100%, 0 100%);
}
```

### 2.4 切角幅度别压字

切角是从右下角切掉一个等腰直角三角形。**幅度必须小于容器内边距**，否则切掉文字。

已核算的安全值：

| 元素 | 宿主内边距 | 建议幅度 |
|---|---|---|
| `.maibot-button` | `8px 16px` | **6px** |
| `.maibot-badge` | `3px 8px` | **4px** |
| 卡片 | `20px` | **不切**（见下） |

**卡片不切角**：切角的语义是「可点击」，卡片是容器不是控件。
容器只靠直角 + 细线表达，这与主题本体一致。

### 2.5 已知脆弱点

判据 2 依赖「主题用了 Saira」这个实现细节。若主题将来换字体，探测会失效（退化成漏判，
配色仍正常）。这是有意的取舍：**不改宿主就拿不到可靠的主题标识**。
如果你需要更强健的方案，正路是给 MaiBot 提 PR，让 `PluginPageContext` 多带一个
主题标识字段——那样所有插件都能做品牌探测，不必猜。

---

## 3. 焦点环：不要写（本节曾是「强制项」，2026-11-23 撤销）

> **变更说明**：本节早期版本要求每个插件都补 `html :focus-visible{… !important}`。
> 该要求已撤销，`char-recog 0.8.4` 与 `cv_lyric_context 2.23.0` 已把各自的焦点规则删除。
> 下面保留的是**事实与层叠原理**（这些仍然成立且值得知道），不再是行动要求。

### 3.1 事实：宿主把焦点框关掉了

`plugin-page-theme.ts:136` 往**每个** iframe 里写死：

```css
:focus,:focus-visible{outline:none!important;--tw-ring-shadow:0 0 #0000!important;
  --tw-ring-offset-shadow:0 0 #0000!important;--tw-inset-ring-shadow:0 0 #0000!important}
```

这段是 SDK 收到 context 后 **append 到 body 末尾**的
（`lib/plugin-custom-page.ts:79` / `:164`），**在你 `<head>` 里的 `<style>` 之后**。

⇒ 自定义页里键盘 Tab **没有焦点提示**。这是宿主的既定行为，主题插件在沙箱外，管不到。

### 3.2 为什么「随手写一条焦点规则」一定是死代码

CSS 层叠顺序是：**先比 `!important` 级别，再比特异性，最后才比书写顺序。**

宿主那条带 `!important`，所以**任何不带 `!important` 的插件声明必输**，特异性再高也没用：

| 写法 | 特异性 | 结果 |
|---|---|---|
| `a:focus-visible{outline:…}`（无 important） | (0,1,1) | ❌ **级别就输了**，特异性高于宿主也没用 |
| `.cvl-input:focus-visible{outline:…}`（无 important） | (0,2,0) | ❌ 同上 |
| `:focus-visible{outline:… !important}` | (0,1,0) | ❌ 同级别同特异性，后写的宿主胜 |
| `html :focus-visible{… !important}` | (0,1,1) | ⚠️ 技术上能赢，但**本契约不建议写** |

两个真实插件都栽在第一行：规则写了、看着挺像样、**从来没渲染过**。
`char-recog 0.8.4` / `cv_lyric_context 2.23.0` 的处理是**删掉**，而不是补 `!important`——
删掉屏幕零变化，只是不再让源文件承诺一个交付不了的东西。

### 3.3 现在的建议

- **不要**在插件页里写 `outline` 焦点规则。写了要么无效（死代码），要么是在跟宿主
  的全局设定对抗，属于超出「主题适配」范围的行为变更，应单独立项讨论。
- **键盘可用性不要依赖焦点环**。如果你的页面有键盘工作流，让「当前项」由
  **你自己的状态**驱动一个可见标记。参考 `char-recog`：待确认队列的当前组由 JS 变量
  `captureFocus` → `.capture-thumb.active` 的边框变色表达，与 CSS 焦点无关，
  所以删掉焦点规则后工作流照常可用。
- 真要在整个 dashboard 层面解决焦点可见性，那是**宿主的事**（给 MaiBot 提 PR），
  不是每个插件各写一遍 `!important` 去覆盖。

---

## 4. 动效（可选，但有硬限制）

主题的机械动效**传不进 iframe**，你只能自己写。两条必须遵守：

1. **`prefers-reduced-motion: reduce` 下必须静止**，且**状态不能丢**。
   把动画放在 `@media (prefers-reduced-motion: no-preference)` 里，
   静止态本身要能表达「进行中」（常亮的点 + 旁边文字），不要靠动画才有意义。

2. **不做持续循环的装饰动画**。加载指示可以动（它在表达真实状态），
   但装饰性的呼吸 / 流光不要。

`cv_lyric_context` 现在有一处 `animation: cvl-pulse 1.2s ease-in-out infinite`
（`lyrics.html:87`）**没有任何 reduced-motion 门控** ⇒ 违反第 1 条。

---

## 5. 自检清单

交付前逐条过。**1.3 起的令牌纪律必做；1.1/1.2 组件类看路线；B 层可选；焦点环不写。**

### 底色与文字色（必做，两条路线都要）

- [ ] 页面底色与文字色来自令牌：用 `<body class="maibot-page">`（路线一），
      **或**自己在根容器写 `background/color: var(--maibot-*, 回退值)`（路线二）
- [ ] 所有颜色走 `var(--maibot-*, 回退值)`，没有写死的主色

### 组件类（路线一才做；路线二必须**不做**）

- [ ] 路线一：控件用 `.maibot-button` / `.maibot-card` / `.maibot-input` / `.maibot-select` / `.maibot-badge` / `.maibot-table`
- [ ] 路线二：**零个 `maibot-*` 组件类**（加了会改掉未装主题时的 padding / 字体）

### 令牌纪律（必做，两条路线都要）
- [ ] **没有裸的 `calc(var(--maibot-radius) - Npx)`**，要减就 `max(0px, calc(...))`
- [ ] 装饰性圆角（`999px` / 写死 px）已走令牌或在 B 层压平；真圆点可保留 `50%`
- [ ] 深色用 `html.dark`，不读 `prefers-color-scheme`
- [ ] 没有 `<link href>` 引外部 CSS、没有 `fetch()`、没有外链图片 / 字体（CSP 会拦）

### 焦点环（2026-11-23 起：不写）

- [ ] **没有**任何 `outline` 焦点规则（宿主全局关闭，写了是死代码，见第 3 节）
- [ ] 若有键盘工作流，「当前项」由自己的状态驱动可见标记，不依赖 CSS 焦点

### B 层（可选）

- [ ] 探测用「圆角归零 + 宽体拉丁」两条，**不用饱和度**
- [ ] 监听 `maibot:context`，不只判一次
- [ ] 所有 B 层规则带 `html[data-ef-page='on']` 门控
- [ ] 切角幅度 < 容器内边距（按钮 6px / 徽章 4px），卡片不切
- [ ] 关掉主题后页面恢复官方观感（切角消失，配色回官方）

### 动效（若写了）

- [ ] 循环动画在 `prefers-reduced-motion: no-preference` 块内
- [ ] 静止态仍能表达状态，不依赖动画

---

## 6. 对照样例：两个真实插件（已按本契约改造）

初次分析时是只读的（`char-recog` 0.8.3 / `cv_lyric_context` 2.22.0）。
**2026-11-23 已落地改造**：`char-recog` **0.8.4**、`cv_lyric_context` **2.23.0**。
下表「改造前 → 改造后」两列都保留，方便看出每一步做了什么。

### 6.1 char-recog — A 层本来就达标，只删了死代码

| 项 | 改造前（0.8.3） | 现在（0.8.4） |
|---|---|---|
| `maibot-page` | ✅ `<body class="maibot-page">` | ✅ 不变 |
| 宿主组件类 | ✅ **8 个**（button/card/input/select/badge/table/inset/page） | ✅ 不变 |
| 令牌消费 | ✅ **12 种**，`:root` 映射成 `--bg`/`--surface`/`--ink` 等别名 | ✅ 不变 |
| 圆角走令牌 | ⚠️ 10 处走令牌，但 `.capture-thumb img` 有 **1 处负值 calc**（早期文档误记为「无」） | ⚠️ 仍在（主题下取初始值 0，属隐患非现症，未列入该轮范围） |
| 硬编码色 | ⚠️ 3 个，都在 `#character-select option` —— 原生下拉弹层兜底，**有正当理由** | ⚠️ 不变 |
| 焦点环 | ❌ 一条**永不生效**的规则（无 `!important`） | ✅ **已删**，7 个页面全清 |
| B 层切角 | ❌ 无 | ❌ 无（可选，不算缺陷） |

**为什么只删不补**：那条 `a:focus-visible,input[type=checkbox]:focus-visible{outline:2px solid var(--accent)}`
没有 `!important`，在层叠的**级别**上就输给宿主，特异性 (0,1,1) > (0,1,0) 也救不回来
⇒ 从来没渲染过。删掉屏幕零变化。

**键盘工作流为什么不受影响**（已逐条核实）：当前组标记来自 JS 变量 `captureFocus`
→ `.capture-thumb.active` 的边框变色，**不是** CSS 焦点；全文无 `.focus()` 调用；
`1`/`2`/空格/`u` 快捷键不移动焦点。

**⚠ 改哪个文件**：`webui/images.html` 等 6 个页面是 **`webui/build.py` 生成的**
（文件头写着 `Generated by webui/build.py; edit webui/index.html`）。
必须改**源文件 `webui/index.html`**，再跑 `python webui/build.py` 重新生成，
否则下次构建会把改动覆盖掉。

### 6.2 cv_lyric_context — 吃到颜色吃不到形状，已补形状跟随

| 项 | 改造前（2.22.0） | 现在（2.23.0） |
|---|---|---|
| 令牌消费 | ✅ **12 种全带回退值**（`:7-18`，深色另有 `:39-44`） | ✅ 不变 |
| `maibot-page` | ❌ 无 | ❌ **仍不加**（见下方说明） |
| 宿主组件类 | ❌ 0 个，全用自有 `.cvl-*` | ❌ **仍不加**（见下方说明） |
| 派生圆角负值 | ❌ **7 处** `calc(var(--cvl-round) - 2px/4px)`（早期文档误记为 4 处） | ✅ 7 处全部 `max(0px, calc(...))` |
| 写死圆角 | ❌ logo `11px`、徽章与进度条 `999px` | ✅ 门控内压成直角；`50%` 状态点保留 |
| 焦点环 | ❌ 一条永不生效的规则 | ✅ **已删** |
| reduced-motion | ❌ 裸循环 `cvl-pulse 1.2s infinite` | ✅ 包进 `no-preference`，静止时颜色仍表达「正在同步」 |
| 选中态 | `box-shadow: 0 0 0 1px` 外发光 | ✅ 门控内换成 1px 细线 |
| B 层切角 | ❌ 无 | ❌ 无（本轮未做切角，只压形状） |

**★ 为什么不加 `maibot-page` 和组件类（重要，与直觉相反）**：
宿主组件类是**无条件注入**的（`plugin-page-theme.ts:120-130`，跟风格、跟装没装主题**都无关**），
而且 `:133`/`:137` 写死了 `.maibot-button{padding:8px 16px}` / `.maibot-card{padding:20px}`。
⇒ **加类会连「没装主题时」的内边距和字体一起改掉**。本轮的硬约束是「没装主题时保持原样」，
所以走的是**只用令牌 + 门控 CSS**的路线，一个组件类都没加。

这也是对第 1.1/1.2 节的重要补充：**那两节适用于「愿意全面接受宿主组件观感」的插件**；
如果你的插件已有一套自洽的视觉、只想在方角主题下跟着变方，**不要加组件类**，
改用第 2 节的探测门控，只覆盖形状属性。

**探测判据实测**：主题 4 强调色 × 3 纸色 × 2 模式 = **24 组漏判 0**；
官方 modern / millennium / future-retro **误判 0**（复古风字体含 Bahnschrift，
是最易误判的一组，靠「圆角非 0」被正确排除）。

### 6.3 两者对比的启示

| | char-recog | cv_lyric_context |
|---|---|---|
| 令牌桥接 | ✅ | ✅（回退值更规范） |
| 组件类 | ✅ 8 个（全面接受宿主观感） | ❌ 0 个（**有意为之**，保护未装主题时的外观） |
| 形状跟随主题 | ✅ 自动 | ✅ 靠门控层补 |
| 负值 calc | 1 处（隐患，未修） | 7 处 → **已全钳** |
| reduced-motion | ✅ 一直有 | ❌ → ✅ **已补** |

两条可复用的结论：

1. **同一个作者的两个插件，A 层达标度差这么远** ⇒ 不是能力问题，是「有没有清单」。
   这正是本文档存在的理由：把隐式约定写成显式清单。
2. **「适配主题」有两条路，选哪条取决于你要不要保住未装主题时的样子**：
   全面接受宿主组件类（省事，但外观交给宿主），或只用令牌 + 门控（工作量稍大，
   但能精确控制「装主题才变」）。**不存在两全的第三条路**——加类必然影响未装主题时。

---

## 7. 文件清单

| 文件 | 用途 |
|---|---|
| `docs/plugin-page-adaptation.md` | 本文，契约 + 清单 + 对照 |
| `docs/examples/example.html` | 最小可抄样例（**路线一**：用宿主组件类） |
| `docs/examples/endfield-page-adapter.js` | 能力探测完整版（含判据理由与实测结论） |
| `docs/examples/endfield-page.css` | 可选 B 层片段，全部带门控 |

**这些文件不参与主题运行时**，主题不会去读它们，也不会注入到你的插件里。
它们是给开发者抄的。用法：把 `endfield-page.css` 与 `endfield-page-adapter.js`
的内容**内联**进你自己的 `webui/*.html`（CSP 禁止外链）。

**路线二的现成参考不在本目录**，直接读已落地的真实实现：
`cv_lyric_context` 2.23.0 的 `webui/lyrics.html` —— 探测脚本在 `<script>` 开头，
形状跟随层在 `<style>` 末尾（8 行，全部带 `html[data-ef-page='on']` 门控），
零个宿主组件类。它的 `tests/test_webui_pages.py` 里还有 7 个可直接抄的守护用例。

---

## 8. 出处速查

| 机制 | 源码位置（MaiBot 1.4.8） |
|---|---|
| iframe 沙箱 | `components/plugin-custom-page.tsx:474-480` |
| CSP | `lib/plugin-custom-page.ts:54-57` |
| 11 项属性白名单 | `lib/plugin-page-theme.ts:2-14` |
| 13 个令牌 | `lib/plugin-page-theme.ts:95-118` |
| 5 组组件类 | `lib/plugin-page-theme.ts:120-130` |
| 页面基类 `.maibot-page` | `lib/plugin-page-theme.ts:132` |
| **焦点框被关闭** | `lib/plugin-page-theme.ts:136` |
| 字体白名单（4 个） | `lib/plugin-page-theme.ts:28-37` |
| SDK 应用 context | `lib/plugin-custom-page.ts:71-79` |
| themeStyle 追加到 body | `lib/plugin-custom-page.ts:79` / `:164` |
| 探针元素 | `components/plugin-custom-page.tsx:422-435` |
| 千禧卡片不改圆角 | `styles/millennium.css:228-235` |
| 官方 radius 基准 | `index.css:340`（`--visual-radius-lg: 0.5rem`） |