# 插件自定义 WebUI 页面适配终末地主题

面向 **MaiBot 插件开发者**。你的插件有 `webui.json` 里 `mode: "custom"` 的页面时，  
按本文做，页面就能跟着 endfield-theme（以及任何官方风格）变色变形。

本文所有机制均以 **MaiBot 1.4.8 / dashboard 源码**核对，行号可复查。

> **★ 你不需要装本主题，也不需要拿到任何示例插件仓库。**  
> 所有可抄的东西都在 [`examples/`](./examples/) 里，**自包含、复制即用**：

> | 你要什么                | 拿哪个文件                                                                                                                                  |
> | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
> | 一个能直接当起点的完整页面       | [`examples/route2-page.html`](./examples/route2-page.html)（路线二）<br />[`examples/example.html`](./examples/example.html)（路线一）           |
> | 只要形状跟随的 CSS 片段      | [`examples/route2-shape.css`](./examples/route2-shape.css)（路线二）<br />[`examples/endfield-page.css`](./examples/endfield-page.css)（路线一） |
> | 探测脚本                | [`examples/endfield-page-adapter.js`](./examples/endfield-page-adapter.js)                                                             |
> | 守护用例（放进你的 `tests/`） | [`examples/test_page_adaptation.py`](./examples/test_page_adaptation.py)                                                               |
> | 交付前自检               | [`check_page_adaptation.py`](./check_page_adaptation.py)（零依赖，`python` 直接跑）                                                             |
>
> 第 6 节提到的四个真实插件是**作者本地的实测记录**（用来证明这些结论不是纸上推演），  
> **不公开、不是必读**。凡「去读某插件某文件」的指路都已改为指向上表的自包含文件。

## 责任边界：谁改什么

**适配是插件开发者自己的事。主题侧提供方法与工具，不代改任何插件的代码。**

| 事项 | 谁负责 | 说明 |
|---|---|---|
| 配色跟随（走 `--maibot-*` 令牌） | **插件开发者** | 必做。做了就同时适配官方三风格，不装本主题也该做 |
| 圆角钳位、深色判据、CSP 合规 | **插件开发者** | 必做。见 1.3–1.6 |
| 写死装饰圆角压平 / 语义圆点保留 | **插件开发者** | 必做。片段与断言已备好 |
| 既有真焦点环的保留 | **插件开发者** | 只有你自己知道那条是不是真能力 |
| **切角 / 眉标（B 层）** | **插件开发者，纯自愿** | **不做不算缺陷**，自检脚本不会因此报问题。见第 2 节 |
| 自定义控件（下拉/弹窗）替换 | **插件开发者** | 涉及业务逻辑与取舍，主题侧无法代做。方法见 6.1 |
| 提供令牌桥、组件类、探测判据 | 宿主 + 本主题 | 已完成，你直接消费 |
| 提供契约文档、样例、自检与证明工具 | 本主题 | 就是本目录这些文件 |

**主题侧不会做的事**：不会去改你的 `webui/*.html`，不会替你决定要不要 B 层，
也不会因为你没做 B 层而判你不合规。**沙箱隔离决定了主题根本碰不到你的页面**
（见第 0 节）—— 这既是限制，也是你的页面不会被主题意外改坏的保证。

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

| 你想做的事                              | 能不能                            |
| ---------------------------------- | ------------------------------ |
| 内联 `<style>` / `<script>`          | ✅ 能（`unsafe-inline`）           |
| `<link href="xxx.css">` 引外部样式      | ❌ **不能**（`default-src 'none'`） |
| `fetch()` 拿任何东西                    | ❌ **不能**（`connect-src 'none'`） |
| `<img src="https://...">`          | ❌ 不能，只能 `data:` / `blob:`      |
| `@font-face src: url(https://...)` | ❌ 不能，只能 `data:`                |
| 读父页面 DOM / 主题变量                    | ❌ 不能                           |

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

| 令牌                            | 采样来源                            |
| ----------------------------- | ------------------------------- |
| `--maibot-background`         | 背景探针 `bg-background`            |
| `--maibot-surface`            | Card 背景                         |
| `--maibot-foreground`         | Card 文字                         |
| `--maibot-muted`              | `text-muted-foreground`         |
| `--maibot-soft`               | Input 背景（透明则回退 `bg-muted`）      |
| `--maibot-border`             | Card 上边框色                       |
| `--maibot-primary`            | Primary 按钮背景                    |
| `--maibot-primary-foreground` | Primary 按钮文字                    |
| `--maibot-danger`             | Danger 按钮背景                     |
| `--maibot-radius`             | Card 圆角                         |
| `--maibot-font-body`          | Card 字体族                        |
| `--maibot-font-display`       | 风格标题字体（回退 Card 字体）              |
| `--maibot-font-mono`          | `--typography-font-family-code` |

外加 **5 组组件类规则**（`:120-130`）：`.maibot-button`（含 primary / danger / `[aria-pressed=true]`）、  
`.maibot-card`、`.maibot-input` / `.maibot-select` / `.maibot-inset`，  
以及页面基类 `.maibot-page`。

### 什么传得进、什么传不进

| 主题特征                  | 自动传入 | 说明                       |
| --------------------- | ---- | ------------------------ |
| 配色（纸 / 墨 / 强调色 / 危险色） | ✅    | 走令牌                      |
| **圆角归零**              | ✅    | `border-radius` 在白名单里    |
| **柔和阴影归零**            | ✅    | `box-shadow` 在白名单里       |
| 字体族名                  | ⚠️   | 名字传得进，**字体文件传不进**（见下）    |
| **切角 `clip-path`**    | ❌    | 不在 11 项里                 |
| `//` 眉标、等高线底纹         | ❌    | 伪元素 / 背景图，采样不到           |
| 机械动效、保存黄穿反馈           | ❌    | 依赖父页 DOM 观察，跨沙箱做不到       |
| 焦点环                   | ❌    | **宿主主动关掉**，插件侧不要写，见第 3 节 |

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

> |       | 路线一：全面接受宿主观感                                       | 路线二：只跟形状，保住原样                                              |
> | ----- | -------------------------------------------------- | ---------------------------------------------------------- |
> | 做法    | 用 `maibot-page` + 宿主组件类（1.1 / 1.2）                 | 只用令牌（1.3）+ 第 2 节探测门控                                       |
> | 未装主题时 | 外观**由宿主决定**（padding / 字体被组件类接管）                    | 外观**与改造前逐像素一致**                                            |
> | 适合    | 新页面，或愿意把观感交给宿主                                     | 已有一套自洽视觉的成熟页面                                              |
> | 现成样例  | [`examples/example.html`](./examples/example.html) | [`examples/route2-page.html`](./examples/route2-page.html) |
>
> **关键事实**：宿主组件类是**无条件注入**的（`plugin-page-theme.ts:120-130`，  
> 与风格、与是否装主题都无关），且 `:133`/`:137` 写死了 padding。  
> 所以「加组件类」和「没装主题时外观不变」**不可能同时成立**。  
> 选路线二就**别加组件类**，完整写法见  
> [`examples/route2-page.html`](./examples/route2-page.html)（可直接双击预览）。
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
（见 [`examples/route2-page.html`](./examples/route2-page.html) 的 `.demo-root`，  
它不加 `maibot-page` 也不会翻车）。  
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

现成写法见 [`examples/route2-page.html`](./examples/route2-page.html) 的 `.demo-thumb`；  
守护断言见 [`examples/test_page_adaptation.py`](./examples/test_page_adaptation.py)  
的 `test_radius_calc_never_goes_negative`（配置区填你自己的圆角别名即可）。

> 作者本地实测记录（**这些插件不公开，仅供说明这不是纸上推演**）：  
> 四个真实插件分别有 7 / 10 / 5 / 1 处未钳住的负 calc，2026-11-23 已全部钳住。  
> 详见第 6 节。

⚠ **一个必须纠正的常见误解**：不要以为「裸 `var(--maibot-radius)` 没写回退值 ⇒  
没装主题时变量不存在 ⇒ 圆角一直是 0」。**宿主令牌是无条件注入的**  
（`lib/plugin-page-theme.ts:95-118`，从 dashboard 自己的卡片/按钮上 `getComputedStyle`  
实测采样，与装没装主题无关）。官方三风格卡片圆角实测为  
**8px（modern）/ 0px（millennium）/ 4px（future-retro）**  
（`lib/theme/tokens.ts:254 / 558 / 431`，Card 用 `rounded-lg`）。  
所以裸引用在没装主题时拿到的是正常的 8px，**不是现症**。  
回退值仍建议写（SDK 送 context 前有一小段空窗），但它不是「圆角消失」的原因。

### 1.5 ⚠ 装饰性圆角要自己收

`border-radius: 999px`（胶囊）、`50%`（圆点）、`11px`（写死）这些**主题管不到**。  
主题语法是「圆角全零」，所以要么改成走令牌，要么在 B 层门控里压平。

例外：**真正的圆点**（状态灯、进度点）保留 `50%` 是合理的——  
主题本体也保留圆形状态点。判断标准是「它是不是一个点」，不是「它圆不圆」。

可直接抄的门控片段：[`examples/route2-shape.css`](./examples/route2-shape.css)  
（路线二，占位选择器，含「刻意不压的两类」说明）；  
路线一用 [`examples/endfield-page.css`](./examples/endfield-page.css)。  
配套断言 `test_hardcoded_round_is_flattened_under_gate` 与  
`test_semantic_dots_stay_round` 在  
[`examples/test_page_adaptation.py`](./examples/test_page_adaptation.py) 里。

### 1.6 深色不要自己猜

SDK 会把深浅同步成 iframe 内的 `html.dark`（`lib/plugin-custom-page.ts:73`）。  
写 `html.dark { … }` 即可，**不要**去读 `prefers-color-scheme`——  
用户在 dashboard 里手动选的深浅与系统设置可能不一致。

---

## 2. B 层（可选）：切角与眉标，条件生效

想要「终末地味」而不只是「跟着变色」，才做这一层。

> **★ 这一层完全由插件开发者自己决定，主题侧不代做、也不检查你有没有做。**
> 不做 B 层**不算适配缺陷** —— 配色与走令牌的圆角已经自动跟随（A 层），
> 页面在方角主题下已经是协调的。切角/眉标只是「想更像终末地」的加味。
> 自检脚本不会因为你没做 B 层而报任何问题。
>
> 现成片段：[`examples/route2-shape.css`](./examples/route2-shape.css) 第 6 段
> （路线二）/ [`examples/endfield-page.css`](./examples/endfield-page.css) 第 1–2 段（路线一）。
> **不要就整段删掉**，两份片段都是这么设计的。

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

| 场景              | 期望   | 实测       |
| --------------- | ---- | -------- |
| 主题在，24 组合       | 全部命中 | **漏判 0** |
| 官方 modern       | 排除   | ✅        |
| 官方 millennium   | 排除   | ✅        |
| 官方 future-retro | 排除   | ✅        |

宁可漏判不可误判：漏判只是少了切角（配色仍自动跟随），误判会污染没装主题的用户。

### 2.3 探测代码

三份都是自包含的，任选其一复制：

| 文件                                                                         | 形态                  |
| -------------------------------------------------------------------------- | ------------------- |
| [`examples/endfield-page-adapter.js`](./examples/endfield-page-adapter.js) | 独立完整版，含判据理由与实测结论    |
| [`examples/example.html`](./examples/example.html)                         | 路线一页面里的内联版          |
| [`examples/route2-page.html`](./examples/route2-page.html)                 | 路线二页面里的内联版（与四插件同口径） |

⚠ **CSP 禁外链** ⇒ 只能内联，不能 `<script src>`。多页插件每页内联一份，  
**副本必须逐字节一致**（用 `test_probe_and_gate_identical_across_pages` 钉住）。

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
/* 路线一：压宿主组件类 */
html[data-ef-page='on'] .maibot-button {
  clip-path: polygon(0 0, 100% 0, 100% calc(100% - 6px), calc(100% - 6px) 100%, 0 100%);
}
/* 路线二：压你自己的类（不加宿主类） */
html[data-ef-page='on'] .your-badge { border-radius: 0; }
```

现成片段：路线一 [`examples/endfield-page.css`](./examples/endfield-page.css)、
路线二 [`examples/route2-shape.css`](./examples/route2-shape.css)。
两份都是**纯增量**——每条带门控，没装主题时整层不生效。

### 2.4 切角幅度别压字

切角是从右下角切掉一个等腰直角三角形。**幅度必须小于容器内边距**，否则切掉文字。

已核算的安全值：

| 元素               | 宿主内边距      | 建议幅度       |
| ---------------- | ---------- | ---------- |
| `.maibot-button` | `8px 16px` | **6px**    |
| `.maibot-badge`  | `3px 8px`  | **4px**    |
| 卡片               | `20px`     | **不切**（见下） |

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
> 该要求已撤销（作者本地两个插件已把各自的死焦点规则删除）。  
> 下面保留的是**事实与层叠原理**（这些仍然成立且值得知道），不再是行动要求。
>
> ⚠ **撤销的是「强制新写」，不是「删掉已有的」**：如果你页面里已有一条
> **带 `!important` 且真在渲染**的焦点环，那是既有键盘能力，
> **做形状适配时不要顺手删它**（删了是真功能退化）。
> 正例见 [`examples/route2-page.html`](./examples/route2-page.html) 的
> `.demo-root :focus-visible`；守护断言 `test_existing_focus_ring_is_preserved`
> 在 [`examples/test_page_adaptation.py`](./examples/test_page_adaptation.py) 里。

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

| 写法                                                 | 特异性     | 结果                     |
| -------------------------------------------------- | ------- | ---------------------- |
| `a:focus-visible{outline:…}`（无 important）          | (0,1,1) | ❌ **级别就输了**，特异性高于宿主也没用 |
| `.cvl-input:focus-visible{outline:…}`（无 important） | (0,2,0) | ❌ 同上                   |
| `:focus-visible{outline:… !important}`             | (0,1,0) | ❌ 同级别同特异性，后写的宿主胜       |
| `html :focus-visible{… !important}`                | (0,1,1) | ⚠️ 技术上能赢，但**本契约不建议写**  |

作者本地两个真实插件都栽在第一行：规则写了、看着挺像样、**从来没渲染过**。  
处理是**删掉**，而不是补 `!important`——删掉屏幕零变化，
只是不再让源文件承诺一个交付不了的东西。

判定脚本：`check_page_adaptation.py` 的 `FOCUS-DEAD`（现症）与 `FOCUS-REAL`（提示）；
守护断言 `test_no_dead_focus_ring`。**先判断它到底有没有生效，再决定删不删。**

### 3.3 现在的建议

- **不要**在插件页里写 `outline` 焦点规则。写了要么无效（死代码），要么是在跟宿主  
  的全局设定对抗，属于超出「主题适配」范围的行为变更，应单独立项讨论。
- **键盘可用性不要依赖焦点环**。如果你的页面有键盘工作流，让「当前项」由  
  **你自己的状态**驱动一个可见标记：JS 里记一个 `currentIndex`，
  渲染时给对应项加 `.is-current`，用边框/底色变化表达，与 CSS 焦点无关。
  这样删掉焦点规则后工作流照常可用（作者本地插件已逐条核实过这条路径）。
- **已有的真焦点环例外**：带 `!important` 且真在渲染的那条是既有能力，保留它，
  连它自身的 `border-radius`（焦点框形状，不是装饰圆角）一起保留。
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

正确写法见 [`examples/route2-shape.css`](./examples/route2-shape.css) 第 7 段
与 [`examples/route2-page.html`](./examples/route2-page.html) 的 `demo-pulse`：
无限动画整块包在 `no-preference` 里，用户要求减少动效时元素保持常亮，
状态由旁边文字/颜色表达，**不会失显**。
守护断言 `test_pulse_animation_respects_reduced_motion`。

> 作者本地实测：某插件曾有一处裸 `animation: … 1.2s ease-in-out infinite`
> 无任何门控，违反第 1 条，已修。

---

## 5. 自检清单

交付前逐条过。**1.3 起的令牌纪律必做；1.1/1.2 组件类看路线；B 层可选；焦点环不写。**

### 5.0 先跑脚本，再人工过清单

配套自检脚本：[`check_page_adaptation.py`](./check_page_adaptation.py)（零依赖，只用标准库）。

```bash
python docs/check_page_adaptation.py <你的插件目录>
python docs/check_page_adaptation.py <你的插件目录> --json     # 机器可读
python docs/check_page_adaptation.py <你的插件目录> --strict   # 隐患也算失败
python docs/check_page_adaptation.py --selftest               # 脚本自测（30 项）
```

改了脚本本身**必须先跑 `--selftest`**：它用合成样例覆盖 30 条判据，  
不依赖任何外部插件，任何人都能复验。每条都对应一个真实踩过的坑。
脚本**零第三方依赖**（只用 `argparse` / `json` / `pathlib` / `re` / `sys` 五个标准库），
系统 Python 直接跑，不用建虚拟环境（无 `match` / `:=` / 内建泛型注解等新语法）。

退出码：`0` 无现症 / `1` 有现症（`--strict` 下隐患也算）/ `2` 用法或目录错误。  
只有配置页、没有自定义页的插件会直接告诉你「无需适配」——宿主渲染，主题已自动接管。

**三档分级，别把隐患当现症改**：

| 级别     | 含义               | 例子                             |
| ------ | ---------------- | ------------------------------ |
| **现症** | 现在就在屏幕上出错        | 白字配荧光强调色、死焦点环、探测按品牌判、跨页副本漂移    |
| **隐患** | 现在恰好正常，换个风格/令牌就崩 | 负圆角（方角下碰巧仍是方角）、写死装饰圆角、无限动画无门控  |
| **提示** | 需要你自己判断，不是缺陷     | `50%` 是不是真圆点、宿主控件类要不要留、真生效的焦点环 |

**脚本查什么**：负圆角钳位（区分现症/隐患）、白字对比度（追溯变量定义链）、  
写死装饰圆角、门控缺失、死焦点环 vs 真焦点环、宿主控件类（只扫 `class` 属性内）、  
探测完整性与跨页一致性、生成源与产物漂移、CSP 违规、深浅判据、动效门控、body 片段。

**⚠ 脚本证明不了交互行为**。它只做静态扫描。涉及自定义控件（下拉、弹窗、拖拽）时  
**必须另做真实浏览器验收**：真实 `iframe` + 真实沙箱 + 真实 CSP + 最小宿主桥桩。  
实例（作者本地实测）：某插件把 8 个原生下拉换成自定义面板，静态用例全绿，
真实浏览器验收却抓出 **3 个真 bug** —— `value` / `hidden` / `disabled` 都是 IDL 属性，
赋值**不改 attribute**，`MutationObserver` 抓不到，
导致面板文案不更新 / 该隐藏的没隐藏 / 该禁用的还能点。详见第 6.1 节。

**脚本自身经过双向回测**（22/22）：拿四个真实插件的**改前**版本验证能抓出已知缺陷
（负圆角 7 / 10 / 5 / 1 处、以及一处白字 bug），再拿**改后**版本验证清零；
同时钉住三条**不许误报**的底线：

1. **写死的强调色不跟随主题** ⇒ 不许报成「现症·装主题才坏」。  
   例：`--x-accent: #1baf7a` 是写死绿。只看变量名含 `accent` 就判违规是错的，
   **必须追溯定义链**。它配白字实测 **2.82**，确实低于 WCAG AA 对大字号/图形的 3.0 ——  
   但那是**既有配色问题**，脚本只给「提示」，不谎报成适配缺陷；
2. 文字色取 `var(--maibot-primary-foreground)` 是**正确写法**（宿主配套前景色，  
   装主题后自动变墨字）⇒ 不许报，更不能展开成回退值 `#ffffff` 去算对比度；
3. `var(--maibot-muted)` 是**颜色令牌**，`.maibot-muted` 是**类** ⇒ 同名不同物，  
   类名检查只扫 `class` 属性内。

另有三条**「注释不是代码」**的底线（做样例页时抓出来的）：注释里的反面示范
（`✗ border-radius: calc(...)`）、解释文字（「不要读 prefers-color-scheme」）
都不许被判成违规；已被门控压平的写死圆角是**正确做法**，不许再报隐患；
焦点框自身的圆角不是装饰圆角，只给提示。

### 5.0b 守护用例：把结论变成机器保证

[`examples/test_page_adaptation.py`](./examples/test_page_adaptation.py)
是**可直接抄的 pytest 模板**，放进你的 `tests/`，改顶部配置区几行即可。

> **依赖说明**：这份模板需要 **pytest**（`pip install pytest`）——
> 这是本套交付物里**唯一**需要装的东西。
> 两份脚本（`check_page_adaptation.py` / `prove_no_theme_change.py`）**零依赖**，
> 系统 Python 直接跑。如果你不想装 pytest，只跑那两份脚本也能覆盖大部分判据；
> 用例模板的增量价值是「**跨页逐字节一致**」与「**数量变化要被 review**」这类
> 需要钉住具体数值的断言。

```python
PAGES = ("main",)                    # 你的自定义页文件名（多页全列上）
ROUND_TOKENS = ("--your-round",)     # 你的圆角别名
EXPECTED_CLAMPED_COUNT = 1           # 派生圆角预期总数（数量变化要被 review）
SEMANTIC_DOTS = (".your-dot",)       # 语义圆点：50% 必须保留
HARDCODED_ROUND = (".your-badge",)   # 写死圆角：必须门控压平
REAL_FOCUS_RING = ".your-root :focus-visible"   # 既有真焦点环，没有填 None
ALLOWED_HOST_CLASSES = ()            # 路线二填 ()；只留根容器填 ("maibot-page",)
ROUTE_ONE = False                    # 走路线一置 True（放行所有 maibot-* 类）
```

14 个用例，未配置的项自动 skip。每条都对应一个真实踩过的坑，docstring 里写了原因。
**它守的是「适配做对了」，不是「代码能跑」**——后者由你原有功能测试负责。

模板本身经过两轮反向验证（对路线二样例 15/15、对片段配套 16/16），
过程中修掉它自己 4 个真缺陷：注释被当代码（2 处）、
「门控行出现圆点类名」误判「给圆点加动画」、
焦点环用子串判断导致规则删了仍「找到」。**这些坑你抄的时候已经躲过了。**

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

### 焦点环（2026-11-23 起：不新写）

- [ ] **没有新写**不带 `!important` 的 `outline` 焦点规则（宿主全局关闭，那是死代码，见第 3 节）
- [ ] 若**已有**带 `!important` 且真生效的焦点环：**保留**它（连它自身的圆角一起）
- [ ] 若有键盘工作流，「当前项」由自己的状态驱动可见标记，不依赖 CSS 焦点

### B 层（**纯自愿，整节跳过不算缺陷**）

**不做 B 层不用过这个清单。** 只有你决定要做时才逐条对：

- [ ] 探测用「圆角归零 + 宽体拉丁」两条，**不用饱和度**
- [ ] 监听 `maibot:context`，不只判一次
- [ ] 所有 B 层规则带 `html[data-ef-page='on']` 门控
- [ ] 切角幅度 < 容器内边距（按钮 6px / 徽章 4px），卡片不切
- [ ] 关掉主题后页面恢复官方观感（切角消失，配色回官方）

⚠ 注意：**形状跟随（压写死圆角）虽然也用同一个门控，但它属于必做项**
（见 1.5 与上面「令牌纪律」），不要因为「B 层可选」就把它一起跳过。
两者共用探测脚本，但责任不同。

### 动效（若写了）

- [ ] 循环动画在 `prefers-reduced-motion: no-preference` 块内
- [ ] 静止态仍能表达状态，不依赖动画

---

## 6. 作者本地实测记录（四个真实插件）

> **⚠ 本节不是必读，也不是抄的对象。**
> 这四个插件是作者本地的私有仓库，**不公开、你拿不到**。
> 保留本节只有一个目的：证明前面那些结论**是在真实插件上验过的**，不是纸上推演，
> 并记下几个只有真机才会暴露的坑。
>
> **要抄代码请去 [`examples/`](./examples/)**（自包含，复制即用）。
> 本节每条教训都已抽成样例里的对应写法或断言，下表给了对照。
>
> **⚠ 别把本节读成「主题作者会帮你改插件」。** 这四次改造是作者在**自己的**插件上
> 做的实验，用来验证契约可行。**主题侧不代改任何第三方插件**（见开头「责任边界」）。
> 你的插件由你自己按本文改，改完跑自检脚本即可。

| 本地插件（版本）                  | 路线                    | 焦点环处理        | 教训                           | 已抽到哪个自包含文件 |
| ------------------------- | --------------------- | ------------ | ---------------------------- | --- |
| `char-recog` 0.9.0        | 一（8 个宿主组件类）           | 删死代码         | **自定义控件替换**（8 个下拉），IDL 属性同步 | 见 6.1 的完整代码片段（可直接抄） |
| `cv_lyric_context` 2.23.0 | 二（零组件类）               | 删死代码         | 门控形状 + 动效门控的标准写法              | `route2-shape.css` |
| `self-identity` 1.12.0    | 二（保留既有 `maibot-page`） | 本来就没有        | **多页副本一致性**（三页内联探测）           | `test_page_adaptation.py` 的跨页断言 |
| `identity-guard` 1.3.0    | 二（零控件类）               | **保住真生效的那条** | 真圆点与焦点框圆角要区别对待                | `route2-page.html` + 两条双向断言 |

四个插件的负 calc 数量分别是 **1 / 7 / 10 / 5** 处，2026-11-23 已全部钳住。
下面「改造前 → 改造后」两列都保留，方便看出每一步做了什么。

### 6.1 char-recog — A 层本来就达标，0.9.0 换了自定义下拉

| 项             | 改造前（0.8.3）                                                     | 现在（0.9.0）                                                          |
| ------------- | -------------------------------------------------------------- | ------------------------------------------------------------------ |
| `maibot-page` | ✅ `<body class="maibot-page">`                                 | ✅ 不变                                                               |
| 宿主组件类         | ✅ **8 个**（button/card/input/select/badge/table/inset/page）     | ✅ 不变                                                               |
| 令牌消费          | ✅ **12 种**，`:root` 映射成 `--bg`/`--surface`/`--ink` 等别名          | ✅ 不变                                                               |
| 圆角走令牌         | ⚠️ 10 处走令牌，但 `.capture-thumb img` 有 **1 处负值 calc**（早期文档误记为「无」） | ✅ 该处已 `max(0px, calc(...))`；其余 10 处裸引用**保持原样**（宿主无条件注入，官方 8px 下正常） |
| 硬编码色          | ⚠️ 3 个，都在 `#character-select option` —— 原生下拉弹层兜底               | ✅ **已删**，改自定义面板，配色全取令牌                                             |
| 焦点环           | ❌ 一条**永不生效**的规则（无 `!important`）                                | ✅ **已删**（0.8.4），7 个页面全清                                            |
| 下拉            | 8 个原生 `<select>`，弹层配色写死                                        | ⚠️ **自定义面板**，跟随令牌与方角；**键盘选择能力移除**（明示取舍）                            |
| B 层切角         | ❌ 无                                                            | ❌ 无（可选，不算缺陷）                                                       |

**★ 自定义控件怎么换才不炸（0.9.0 的做法，值得抄）**：  
8 个下拉在业务 JS 里有 20+ 处 `.value` / `.innerHTML` / `.options` / `.onchange` / `.hidden`  
读写。**不要把原生 `<select>` 换成 `div`** —— 那要重写全部逻辑。  
正确做法是**保留原生元素当数据载体**（视觉隐藏 + `pointer-events:none` + `tabIndex=-1`），  
外面套一层自定义面板驱动它：

- 用户点面板 → 写回 `select.value` → 派发**冒泡** `change` → 既有 `.onchange` 原样触发；
- 业务重写 `innerHTML` → `MutationObserver` 感知 → 面板选项重建；
- 业务写 `.value` / `.hidden` / `.disabled` → **必须覆盖实例访问器**。

**⚠ 最后一条是最容易漏的坑**：这三个都是 **IDL 属性**，赋值**不改 attribute**，  
`MutationObserver` 抓不到。本地实测：静态用例全绿，真实浏览器验收才抓出这 3 个 bug  
（面板文案不更新 / 该隐藏的没隐藏 / 该禁用的还能点）。

**下面这段是自包含的，可以直接抄**（把 `syncPanel` 换成你自己的同步函数）：

```js
// select 是你的原生 <select>；syncPanel(wrap) 负责按 select 当前状态重画面板
function watchNativeSelect(select, wrap, syncPanel) {
  // ① 选项列表变化（业务重写 innerHTML / appendChild）—— 这个 MutationObserver 抓得到
  new MutationObserver(function () { syncPanel(wrap); }).observe(select, {
    childList: true, attributes: true, attributeFilter: ['disabled', 'hidden'],
  });

  // ② ★ value / hidden / disabled 是 IDL 属性：赋值只改内部状态，不改 attribute
  //    ⇒ 上面那个 observer 抓不到。必须取原型描述符，在实例上转发。
  ['value', 'hidden', 'disabled'].forEach(function (key) {
    // hidden 挂在 HTMLElement.prototype，另两个挂在 HTMLSelectElement.prototype
    var owner = key === 'hidden' ? HTMLElement.prototype : HTMLSelectElement.prototype;
    var desc = Object.getOwnPropertyDescriptor(owner, key);
    if (!desc || !desc.set) return;
    Object.defineProperty(select, key, {
      configurable: true,
      get: function () { return desc.get.call(this); },
      set: function (next) { desc.set.call(this, next); syncPanel(wrap); },
    });
  });
}

// ③ 用户点面板选项 → 写回原生值 → 派发**冒泡** change，既有 .onchange 原样触发
function pickOption(select, wrap, value, syncPanel) {
  select.value = value;
  select.dispatchEvent(new Event('change', { bubbles: true }));
  syncPanel(wrap);
}
```

配套 CSS：原生元素**保留在 DOM 里当数据载体**，只做视觉隐藏 ——
`position:absolute; opacity:0; pointer-events:none; width:1px; height:1px`，
再加 `select.tabIndex = -1`。
**不要用 `display:none`**：某些浏览器下它会影响表单提交与 `.options` 行为。

**代价要写进 CHANGELOG**：原生 select 移出 Tab 序列后**键盘选择能力消失**。  
这是明示裁决的取舍，不是遗漏；用一条静态断言把它钉住，将来要恢复必须显式改那条用例。

**为什么只删不补**：那条 `a:focus-visible,input[type=checkbox]:focus-visible{outline:2px solid var(--accent)}`  
没有 `!important`，在层叠的**级别**上就输给宿主，特异性 (0,1,1) > (0,1,0) 也救不回来  
⇒ 从来没渲染过。删掉屏幕零变化。

**键盘工作流为什么不受影响**（已逐条核实）：当前组标记来自 JS 变量 `captureFocus`  
→ `.capture-thumb.active` 的边框变色，**不是** CSS 焦点；全文无 `.focus()` 调用；  
`1`/`2`/空格/`u` 快捷键不移动焦点。

**⚠ 改哪个文件（通用教训）**：如果你的多个页面是 **build 脚本生成的**
（文件头常写着 `Generated by …; edit …`），必须改**源文件**再重跑生成，
否则下次构建会把改动覆盖掉。自检脚本的 `BUILD-STALE` 项专门抓这种漂移。

### 6.2 cv_lyric_context — 吃到颜色吃不到形状，已补形状跟随

| 项              | 改造前（2.22.0）                                               | 现在（2.23.0）                          |
| -------------- | --------------------------------------------------------- | ----------------------------------- |
| 令牌消费           | ✅ **12 种全带回退值**（`:7-18`，深色另有 `:39-44`）                    | ✅ 不变                                |
| `maibot-page`  | ❌ 无                                                       | ❌ **仍不加**（见下方说明）                    |
| 宿主组件类          | ❌ 0 个，全用自有 `.cvl-*`                                       | ❌ **仍不加**（见下方说明）                    |
| 派生圆角负值         | ❌ **7 处** `calc(var(--cvl-round) - 2px/4px)`（早期文档误记为 4 处） | ✅ 7 处全部 `max(0px, calc(...))`       |
| 写死圆角           | ❌ logo `11px`、徽章与进度条 `999px`                              | ✅ 门控内压成直角；`50%` 状态点保留               |
| 焦点环            | ❌ 一条永不生效的规则                                               | ✅ **已删**                            |
| reduced-motion | ❌ 裸循环 `cvl-pulse 1.2s infinite`                           | ✅ 包进 `no-preference`，静止时颜色仍表达「正在同步」 |
| 选中态            | `box-shadow: 0 0 0 1px` 外发光                               | ✅ 门控内换成 1px 细线                      |
| B 层切角          | ❌ 无                                                       | ❌ 无（本轮未做切角，只压形状）                    |

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

### 6.3 self-identity 1.12.0 — 多页副本一致性是重点

三页（`lorebook` / `gallery` / `diagnostics`）共 **10 处**负 calc 全钳，  
三页插入**逐字节一致**的门控 CSS 与探测 JS。既有 `maibot-page` 保留不动。

**★ 多页插件最大的坑是「漏改一页」**：CSP 禁外链 ⇒ 探测代码只能每页内联一份。  
漏改那页**不报错**，只是静默变回圆角，极难发现。  
解法：加一条断言抽出各页探测段做**逐字节比对**，把「副本同步」变成机器保证。  
若有 build 脚本，还要比对**生成源与产物**（改源没重跑 build 同样是静默失效）。

现成断言：`test_probe_and_gate_identical_across_pages`（配置区填 `PAGES` 与锚点即可）。

**⚠ 一个真实的误判教训（值得所有做审计的人记住）**：
看到 `.x-brand-icon{background:var(--x-accent);color:#fff}` 就判「装主题后看不见字」是**错的**。
那个 `--x-accent` 是写死的 `#1baf7a`，**不跟随主题**，白字对比度 2.82 是既有配色问题。  
**变量名里有 `accent` 不代表它跟随主题，必须追溯定义链。**  
反过来，同页另一处 `background: var(--x-primary)` → `var(--maibot-primary)` 才真跟随，
但它的文字色取 `var(--maibot-primary-foreground)`（宿主配套前景色），
装主题后自动变墨字 ⇒ **也是正确写法，不该报**。

这两条已抽成 `test_accent_text_uses_paired_foreground`（内含定义链追溯）
与自检脚本的 `follows_host_token`，你不用自己重推。

### 6.4 identity-guard 1.3.0 — 焦点环的唯一正例

两页共 **5 处**负 calc 全钳。**刻意不删那条焦点环**：

```css
/* 宿主强制 :focus{outline:none!important}，焦点态必须自绘 */
.ig-root :focus-visible {
  outline: 2px solid var(--ig-primary) !important;
  outline-offset: 2px;
  border-radius: 6px;   /* 焦点框自身形状，不是装饰圆角，一并保留 */
}
```

它**带 `!important` 且提高了特异性 ⇒ 真正在渲染**，是既有的键盘可用性能力。  
删它是真功能退化。这与 char-recog / cv_lyric 那两条**不带 `!important`** 的死代码  
性质完全不同 —— **先判断它到底有没有生效，再决定删不删**。

**刻意不压平语义圆点**：状态点的 `50%` 是「这是个点」的语义。  
断言要钉**两个方向**：① 门控层里不许**压平**圆点；  
② **原始规则本身**必须仍是 `50%`（否则有人绕过门控直接改死值，方向 ① 抓不到）。

⚠ 方向 ① 的判定要看**该规则有没有真的声明 `border-radius`**，
不能只看门控行里出现过圆点类名 ——
`html[data-ef-page='on'] .dot.is-running { animation: … }` 是给圆点加动画，完全合法。
（这个误报在做样例时被抓出来并修掉了，见 `test_semantic_dots_stay_round`。）

### 6.5 四者对比的启示


|                | char-recog  | cv_lyric   | self-identity   | identity-guard |
| -------------- | ----------- | ---------- | --------------- | -------------- |
| 令牌桥接           | ✅           | ✅（回退值最规范）  | ✅               | ✅              |
| 组件类            | ✅ 8 个（路线一）  | ❌ 0 个      | 仅 `maibot-page` | ❌ 0 个控件类       |
| 形状跟随           | ✅ 自动 + 面板门控 | ✅ 门控层      | ✅ 门控层           | ✅ 门控层          |
| 负值 calc        | 1 → **已钳**  | 7 → **已钳** | 10 → **已钳**     | 5 → **已钳**     |
| 焦点环            | 死代码 → 删     | 死代码 → 删    | 本来没有            | **真生效 → 保住**   |
| reduced-motion | ✅ 一直有       | ❌ → ✅ 已补   | —               | —              |

三条可复用的结论：

1. **同一个作者的四个插件，A 层达标度差这么远** ⇒ 不是能力问题，是「有没有清单」。  
   这正是本文档与自检脚本存在的理由：把隐式约定写成显式清单。
2. **「适配主题」有两条路，选哪条取决于你要不要保住未装主题时的样子**：  
   全面接受宿主组件类（省事，但外观交给宿主），或只用令牌 + 门控（工作量稍大，  
   但能精确控制「装主题才变」）。**不存在两全的第三条路**——加类必然影响未装主题时。
3. **「未装主题外观不变」可以机器证明，别靠肉眼**：剥掉门控规则后抽  
   `(选择器, 属性, 值)` 三元组做集合差，要求**净新增 0 / 净删除 0**，  
   差异只允许 `max(0px, ...)` 包装（回退值下计算等价）。  
   四个插件都是这么验的（零净变化），本文的两份样例也是这么验的。  
   **现成工具**：[`examples/prove_no_theme_change.py`](./examples/prove_no_theme_change.py)，
   拿改造前后两个文件直接比对，零依赖。
   ⚠ 记得排除 `@keyframes` 内部的关键帧选择器（`0%, 33%`）——
   它们不是页面选择器，定义本身不产生视觉效果，只有被带门控的规则引用时才生效。
   （首轮验证没排除它，误报「净新增 2 条」。）

---

## 7. 文件清单

**全部自包含，不依赖任何插件仓库，也不需要装本主题。**

| 文件 | 用途 |
|---|---|
| [`plugin-page-adaptation.md`](./plugin-page-adaptation.md) | 本文：契约 + 清单 + 实测记录 |
| [`check_page_adaptation.py`](./check_page_adaptation.py) | **自检脚本**（零依赖）：扫你的插件目录，三档分级报告，`--selftest` 30 项 |
| [`examples/example.html`](./examples/example.html) | 完整样例页（**路线一**：用宿主组件类） |
| [`examples/route2-page.html`](./examples/route2-page.html) | 完整样例页（**路线二**：零组件类，只用令牌 + 门控），可双击预览 |
| [`examples/endfield-page.css`](./examples/endfield-page.css) | 形状/风味 CSS 片段（**路线一**口径，压 `.maibot-*`） |
| [`examples/route2-shape.css`](./examples/route2-shape.css) | 形状跟随 CSS 片段（**路线二**口径，压你自己的类），占位选择器 |
| [`examples/endfield-page-adapter.js`](./examples/endfield-page-adapter.js) | 能力探测完整版（含判据理由与实测结论） |
| [`examples/test_page_adaptation.py`](./examples/test_page_adaptation.py) | **守护用例模板**（14 个），改配置区即用（**唯一需要 pytest** 的一项） |
| [`examples/prove_no_theme_change.py`](./examples/prove_no_theme_change.py) | **零净变化证明工具**（零依赖），比对改造前后，`--selftest` 16 项 |

**这些文件不参与主题运行时**，主题不会去读它们，也不会注入到你的插件里。
它们是给开发者抄的。用法：把 CSS 片段与探测脚本的内容**内联**进你自己的
`webui/*.html`（CSP 禁止外链）。

### 7.1 五分钟上手

```bash
# 1. 挑一份完整样例当起点（二选一），把 .demo-* / 宿主类换成你自己的
#    路线二 → examples/route2-page.html    路线一 → examples/example.html

# 2. 只想给已有页面补形状跟随？贴片段 + 探测脚本即可
#    路线二 → examples/route2-shape.css    路线一 → examples/endfield-page.css
#    探测   → examples/endfield-page-adapter.js

# 3. 把守护用例放进你的 tests/，改顶部配置区（这步需要 pytest，其余步骤零依赖）
cp examples/test_page_adaptation.py <你的插件>/tests/

# 4. 交付前自检
python check_page_adaptation.py <你的插件目录>

# 5. 证明「没装主题时外观不变」
python examples/prove_no_theme_change.py 改造前.html 改造后.html
```

### 7.2 按需求挑参考（全部指向本目录）

| 你的需求 | 看哪里 |
|---|---|
| 多页副本一致性 | `test_page_adaptation.py` → `test_probe_and_gate_identical_across_pages`（配置区 `PAGES` + 锚点） |
| 保住真生效的焦点环 | `route2-page.html` 的 `.demo-root :focus-visible` + `test_existing_focus_ring_is_preserved` |
| 语义圆点不被压平 | `route2-page.html` 的 `.demo-dot` + `test_semantic_dots_stay_round`（双向断言） |
| 写死圆角门控压平 | `route2-shape.css` 第 1 段 + `test_hardcoded_round_is_flattened_under_gate` |
| 派生圆角钳位 | `route2-page.html` 的 `.demo-thumb` + `test_radius_calc_never_goes_negative` |
| 动效尊重减少动态效果 | `route2-shape.css` 第 7 段 + `test_pulse_animation_respects_reduced_motion` |
| **自定义控件替换 + IDL 属性同步** | **第 6.1 节的完整代码片段**（已真实浏览器验过 7/7，可直接抄） |
| 证明未装主题外观不变 | `prove_no_theme_change.py` |

> 第 6 节那四个真实插件是**作者本地的私有仓库、不公开**，
> 保留它们只为记录「这些结论在真机上验过」。**你不需要拿到它们**——
> 上表每一条都已抽成本目录里的自包含文件。

---

## 8. 出处速查

| 机制                  | 源码位置（MaiBot 1.4.8）                            |
| ------------------- | --------------------------------------------- |
| iframe 沙箱           | `components/plugin-custom-page.tsx:474-480`   |
| CSP                 | `lib/plugin-custom-page.ts:54-57`             |
| 11 项属性白名单           | `lib/plugin-page-theme.ts:2-14`               |
| 13 个令牌              | `lib/plugin-page-theme.ts:95-118`             |
| 5 组组件类              | `lib/plugin-page-theme.ts:120-130`            |
| 页面基类 `.maibot-page` | `lib/plugin-page-theme.ts:132`                |
| **焦点框被关闭**          | `lib/plugin-page-theme.ts:136`                |
| 字体白名单（4 个）          | `lib/plugin-page-theme.ts:28-37`              |
| SDK 应用 context      | `lib/plugin-custom-page.ts:71-79`             |
| themeStyle 追加到 body | `lib/plugin-custom-page.ts:79` / `:164`       |
| 探针元素                | `components/plugin-custom-page.tsx:422-435`   |
| 千禧卡片不改圆角            | `styles/millennium.css:228-235`               |
| 官方 radius 基准        | `index.css:340`（`--visual-radius-lg: 0.5rem`） |
