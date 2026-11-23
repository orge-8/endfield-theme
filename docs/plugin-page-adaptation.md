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
| 焦点环 | ❌ | **宿主主动关掉**，见第 3 节 |

**字体特例**：`pluginPageFonts()`（`plugin-page-theme.ts:28-37`）只白名单 4 个宿主字体
（Departure Mono / Ark Pixel 12px SC / Jersey 20 / JetBrains Mono），
按 `snapshot.styles` 里出现的族名去 fetch 并转 `data:` 注入。
主题的 **Saira 不在这个白名单里** ⇒ iframe 内 `font-family: "Saira"` 会**回退到系统字体**。
这是已知限制，不是你写错了。想要宽体观感，用 `letter-spacing` + `text-transform` 补，
别指望字体文件能进来。

---

## 1. A 层（必做）：正确消费令牌，配色与直角自动跟随

**这一层不需要装 endfield-theme 也该做**，做了就同时适配官方三风格。

### 1.1 页面根用 `maibot-page`

```html
<body class="maibot-page">
```

它负责把背景 / 文字 / 字体设成当前主题值（`plugin-page-theme.ts:132`）。
**不写这个类，深色主题下你的页面底色会是 iframe 默认白 ⇒ 白底浅字，直接翻车。**

### 1.2 控件用宿主组件类

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
自己写裸 `<button>` 不加类，就只能靠令牌手动上色，形状全丢。

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

负圆角是**非法值，整条声明被丢弃** ⇒ 元素回退到它自己的默认圆角或继承值，
你以为压平了其实没有。`cv_lyric_context` 现在有 4 处这种写法。

正确写法：

```css
border-radius: var(--maibot-radius);          /* 直接用 */
/* 想要层级差就用 clamp 夹住下界 */
border-radius: max(0px, calc(var(--maibot-radius) - 4px));
```

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

## 3. 焦点环（强制项，与主题无关）

**这是无障碍问题，不是风格问题。不装任何主题的插件也该做。**

### 3.1 宿主把焦点框关掉了

`plugin-page-theme.ts:136` 往**每个** iframe 里写死：

```css
:focus,:focus-visible{outline:none!important;--tw-ring-shadow:0 0 #0000!important;
  --tw-ring-offset-shadow:0 0 #0000!important;--tw-inset-ring-shadow:0 0 #0000!important}
```

而且这段是 SDK 收到 context 后 **append 到 body 末尾**的
（`lib/plugin-custom-page.ts:79` / `:164`），**在你 `<head>` 里的 `<style>` 之后**。

⇒ 键盘用户在你的页面上 Tab，**完全没有焦点提示**。主题对此无能为力（沙箱隔离）。

### 3.2 必须 `!important` + 提高特异性，两者缺一不可

CSS 层叠顺序是：**先比 `!important` 级别，再比特异性，最后才比书写顺序。**

- **不带 `!important` ⇒ 必输**，无论你的特异性多高。宿主那条带 `!important`，
  级别上直接压过所有普通声明。（第 6 节两个真实插件都栽在这里。）
- **带了 `!important` 但特异性不高于宿主 ⇒ 也输**，因为同级别时后写的宿主胜。

所以要**两个都做**。

实测特异性（宿主那条是 `(0,1,0)`）：

| 写法 | 特异性 | 结果 |
|---|---|---|
| `a:focus-visible{outline:…}`（无 important） | (0,1,1) | ❌ **级别就输了**，特异性再高也没用 |
| `:focus-visible{outline:… !important}` | (0,1,0) | ❌ 同级别同特异性，后写的宿主胜 |
| `html :focus-visible{… !important}` | (0,1,1) | ✅ |
| `button:focus-visible{… !important}` | (0,1,1) | ✅ |
| `html button:focus-visible{… !important}` | (0,1,2) | ✅ |

**加一个 `html` 前缀就够了**：

```css
html :focus-visible {
  outline: 2px solid var(--maibot-primary) !important;
  outline-offset: 2px;
}
html input:focus-visible,
html select:focus-visible,
html textarea:focus-visible { outline-offset: -1px; }
```

### 3.3 覆盖范围要按能力，不要按类名

别只给 `.maibot-button` 补——你页面里的裸 `<button>`、`<a>`、
`[role=switch]`、`[role=checkbox]`、`[tabindex]` 全都需要。
用上面那条 `html :focus-visible` 兜底最省事。

> 这条教训来自 endfield-theme 0.4.4：主题本体一开始只给 `.dashboard-button` 补焦点环，
> 结果宿主 **205 处裸 `<button>` 一个都没带那个类**，全漏。
> **接管了「关焦点框」这件事，就必须按能力补齐，不能按类名补。**

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

交付前逐条过。**A 层与焦点环是必做，B 层可选。**

### A 层（必做）

- [ ] `<body class="maibot-page">`
- [ ] 控件用 `.maibot-button` / `.maibot-card` / `.maibot-input` / `.maibot-select` / `.maibot-badge` / `.maibot-table`
- [ ] 所有颜色走 `var(--maibot-*, 回退值)`，没有写死的主色
- [ ] **没有 `calc(var(--maibot-radius) - Npx)`**（会算出负值被丢弃）
- [ ] 装饰性圆角（`999px` / 写死 px）已走令牌或在 B 层压平；真圆点可保留 `50%`
- [ ] 深色用 `html.dark`，不读 `prefers-color-scheme`
- [ ] 没有 `<link href>` 引外部 CSS、没有 `fetch()`、没有外链图片 / 字体（CSP 会拦）

### 焦点环（必做）

- [ ] 有 `html :focus-visible { outline: … !important }`（特异性压过宿主）
- [ ] 覆盖裸 `button` / `a` / `input` / `select` / `[role=*]` / `[tabindex]`，不只覆盖组件类
- [ ] 键盘 Tab 走一遍页面，每个可聚焦控件都有可见焦点框

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

## 6. 对照样例：两个真实插件

以下均为**只读分析，未改动任何代码**。分析时版本：
`char-recog` 0.8.3、`cv_lyric_context` 2.22.0。

### 6.1 char-recog（`webui/images.html`，1040 行）— A 层基本达标

| 项 | 状态 | 证据 |
|---|---|---|
| `maibot-page` | ✅ | `<body class="maibot-page">` |
| 宿主组件类 | ✅ **8 个** | `maibot-button` / `card` / `input` / `select` / `badge` / `table` / `inset` / `page` |
| 令牌消费 | ✅ **12 种** | `:root` 里映射成 `--bg` / `--surface` / `--ink` 等自有别名 |
| 圆角走令牌 | ✅ | 10 处 `var(--maibot-radius)`，**无负值 calc** |
| 硬编码色 | ⚠️ 3 个 | `#ffffff` / `#24292f` / `#0b57d0`，都在 `#character-select option` —— 原生下拉弹层兜底，**有正当理由**（原生弹层不受 CSS 变量控制） |
| 焦点环 | ❌ **失效** | 只有 `a:focus-visible, input[type=checkbox]:focus-visible{outline:2px solid var(--accent)}`，**无 `!important`** |
| B 层切角 | ❌ 无 | 未做（可选，不算缺陷） |

**结论**：A 层做得相当好，**配色与直角已经自动跟随主题**。
实质缺口是焦点环——而且不只是覆盖面问题，**现有那条规则本身是失效的**。

**已确证失效**（不是猜测）：它写的 `outline:2px solid var(--accent)` **没有 `!important`**。
CSS 层叠里 **`!important` 级别优先于特异性**——宿主那条带 `!important`，
所以无论插件选择器特异性多高（`a:focus-visible` 是 (0,1,1)，已高于宿主的 (0,1,0)），
**都会输**。特异性只在同 `!important` 级别内才比较。

**最小修法**（一行）：
```css
html :focus-visible { outline: 2px solid var(--accent) !important; outline-offset: 2px; }
```
`!important` 是关键，`html` 前缀是双保险（同级别时特异性 (0,1,1) > (0,1,0)）。

**⚠ 改哪个文件**：`webui/images.html` 等 6 个页面是 **`webui/build.py` 生成的**
（文件头写着 `Generated by webui/build.py; edit webui/index.html`）。
要改**源文件 `webui/index.html`**，然后跑
`uv run --no-sync python webui/build.py` 重新生成，否则下次构建会被覆盖。

### 6.2 cv_lyric_context（`webui/lyrics.html`）— A 层部分达标

| 项 | 状态 | 证据 |
|---|---|---|
| 令牌消费 | ✅ **12 种，且全部带回退值** | `:7-18` 映射成 `--cvl-*`；`:39-44` 另有深色回退 |
| `maibot-page` | ❌ **无** | 全文 0 处 |
| 宿主组件类 | ❌ **一个都没有** | `maibot-button` / `card` / `badge` / … 全部 0 处，全用自有 `.cvl-*` |
| 圆角走令牌 | ⚠️ 混合 | 部分 `var(--cvl-round)`，但有 **4 处 `calc(var(--cvl-round) - 2px/4px)`** ⇒ 主题下算出负值被丢弃 |
| 写死圆角 | ❌ 多处 | `11px`（`:64`）、`999px`（`:76` 胶囊、`:154`/`:155` 进度条）、`50%`（`:80` 状态点，**这个合理**） |
| 焦点环 | ❌ **失效** | `:140` `.cvl-input:focus-visible{outline:2px solid var(--cvl-accent)}`，**无 `!important`** ⇒ 同 6.1 已确证失效；且只覆盖输入框 |
| reduced-motion | ❌ **无门控** | `:87` `animation: cvl-pulse 1.2s ease-in-out infinite` 裸循环 |
| B 层切角 | ❌ 无 | 可选，不算缺陷 |

**结论**：它**吃到了配色**（令牌桥接做得很规范，回退值齐全），
但**吃不到形状**——没用组件类、没用 `maibot-page`，且有一批写死圆角与负值 calc。
所以在主题下呈现的是「终末地的颜色 + 圆角胶囊的形状」。

**按优先级排的修法**：
1. `<body>` 加 `class="maibot-page"`（一行，解决底色 / 字体基线）
2. 4 处负值 calc 改 `max(0px, calc(...))` 或直接用令牌（**这是真 bug，与主题无关**）
3. `:87` 循环动画包进 `prefers-reduced-motion: no-preference`（**无障碍真 bug**）
4. 焦点环换成 `html :focus-visible { … !important }`
5. 胶囊 / 写死圆角走令牌（形状跟随）
6. 控件逐步改用宿主组件类（工作量最大，可分批）

### 6.3 两者对比的启示

| | char-recog | cv_lyric_context |
|---|---|---|
| 令牌桥接 | ✅ | ✅（回退值更规范） |
| 组件类 | ✅ 8 个 | ❌ 0 个 |
| 形状跟随主题 | ✅ | ❌ |
| 负值 calc 隐患 | 无 | **4 处** |
| reduced-motion | ✅ 有门控 | ❌ 无 |

**同一个作者的两个插件，A 层达标度差这么远** ⇒ 说明这不是「能力问题」而是「有没有清单」。
这正是本文档存在的理由：**把隐式约定写成显式清单**。

---

## 7. 文件清单

| 文件 | 用途 |
|---|---|
| `docs/plugin-page-adaptation.md` | 本文，契约 + 清单 + 对照 |
| `docs/examples/example.html` | 最小可抄样例，三层结构齐全 |
| `docs/examples/endfield-page-adapter.js` | 能力探测完整版（含判据理由与实测结论） |
| `docs/examples/endfield-page.css` | 可选 B 层片段，全部带门控 |

**这些文件不参与主题运行时**，主题不会去读它们，也不会注入到你的插件里。
它们是给开发者抄的。用法：把 `endfield-page.css` 与 `endfield-page-adapter.js`
的内容**内联**进你自己的 `webui/*.html`（CSP 禁止外链）。

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