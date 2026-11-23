/* endfield-page-adapter.js — 插件自定义 WebUI 页面的「终末地风味」可选适配层。
 *
 * 用途：把这段内联进你自己的 webui/*.html 的 <script> 里（CSP 禁止外链，见契约文档）。
 * 它只做一件事：探测当前界面是否呈现「直角 + 宽体拉丁」这组特征，
 * 命中就给 <html> 挂 data-ef-page="on"，你的可选 CSS 用这个属性做门控。
 *
 * 为什么需要探测而不是直接判断「装没装 endfield-theme」：
 *   自定义页面跑在 <iframe sandbox="allow-scripts allow-forms"> + srcDoc 里，
 *   没有 allow-same-origin ⇒ opaque origin，读不到父页面任何东西。
 *   宿主只通过探针采样传 13 个 --maibot-* 令牌 + 5 个组件类规则进来
 *   （dashboard/src/lib/plugin-page-theme.ts），里面**没有**「装了哪个主题」这一项。
 *   所以只能做能力探测（看界面长什么样），不能做品牌探测（看是谁装的）。
 *
 * 判据为什么是这两条（实测结论，别自己改）：
 *   1. --maibot-radius 计算值为 0px
 *      —— 主题把 --visual-radius-lg 覆盖成 0px，Card 探针的 border-radius 随之归零。
 *      官方 modern 是 0.5rem；千禧/未来复古**不覆盖这个变量**，且千禧给
 *      [data-dashboard-card] 只改背景/边框/阴影、不动圆角（millennium.css:228-235），
 *      所以这条不会把官方风格误判成主题。
 *   2. --maibot-font-body 里出现宽体拉丁族名（Saira / Bahnschrift 等）
 *      —— 主题把 --typography-font-family-base 改成 "Saira",...，
 *      经 --font-sans 传到 Card 探针的 font-family。
 *      千禧用的是像素字体（Jersey 20 / Departure Mono / Ark Pixel），不在此列。
 *
 *   ⚠ 不要用「强调色是荧光色」当判据：主题**浅色下 --color-primary 是墨色**
 *   （0.0 0.0% 8.6%），只有深色才是荧光。用饱和度判会在浅色下全部漏判。
 *
 * 两条都命中才算，宁可漏判不可误判：漏判只是少了切角（配色仍自动跟随），
 * 误判会让没装主题的用户看到「官方蓝 + 切角」的四不像。
 */
(function () {
  'use strict';

  var WIDE_LATIN = /saira|bahnschrift|saira\s*condensed/i;

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  /** 圆角是否已归零。允许 '0' / '0px' / '0px 0px 0px 0px' 等写法。 */
  function isSquare() {
    var raw = token('--maibot-radius');
    if (!raw) return false;
    var nums = raw.match(/-?[\d.]+/g);
    if (!nums || !nums.length) return false;
    for (var i = 0; i < nums.length; i++) {
      if (parseFloat(nums[i]) !== 0) return false;
    }
    // 带非零单位换算的（如 0.5rem）上面已拦；这里排除 'auto' 之类无数字情形
    return true;
  }

  function hasWideLatin() {
    return WIDE_LATIN.test(token('--maibot-font-body'));
  }

  function apply() {
    var on = isSquare() && hasWideLatin();
    var html = document.documentElement;
    if (on) html.setAttribute('data-ef-page', 'on');
    else html.removeAttribute('data-ef-page');
    // 深浅由宿主 SDK 同步到 html.dark，这里只转发一个便于写 CSS 的标记
    html.setAttribute('data-ef-mode', html.classList.contains('dark') ? 'dark' : 'light');
  }

  // 宿主 SDK 在 ready 后才 postMessage 送 context（初始 srcDoc 里没有主题样式），
  // 所以必须监听 maibot:context，否则首次判定会拿到空令牌。
  window.addEventListener('maibot:context', apply);

  // 兜底：SDK 已就绪但事件早于本脚本执行时，主动读一次。
  if (window.maibot && window.maibot.context && window.maibot.context.styles) apply();
  // 再兜一层：字体异步加载完成后令牌可能才稳定。
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(apply).catch(function () {});
  }
})();