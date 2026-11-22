/* endfield-fx.js — 终末地主题的操作反馈层（L2 注入，随 <script id="endfield-theme-fx"> 进 index.html）。
 *
 * 只做「操作之后」的反馈，不做展示页语法（乱码落定/指针视差/分段圆盘一律不进后台）：
 *   1. flashDone   保存成功 → 黄色穿按钮一次 + 标签「保存」临时变「已保存」1200ms
 *   2. removeRow   表格删行 → 下方行 200ms snap 补位（FLIP，几何在 pointerdown 冻结）
 *   3. toast 增强  提示条被 React 直接卸载时，克隆一份补完向右擦出 160ms（CSS 进出已覆盖，这里兜底）
 *   4. 深浅揭幕    统一接管所有深浅切换入口（侧边栏按钮 / 外观页分段控件 / auth 页按钮），
 *                  View Transitions 圆形揭幕 420ms 机械曲线。官方侧边栏自带的 500ms
 *                  ease-in-out 软曲线被本层替代（WAAPI 优先级高于 CSS，无法只压曲线）。
 *
 * 静止条件（任一满足即全部不动）：
 *   - prefers-reduced-motion: reduce
 *   - html[data-ef-motion='calm']（动效变体：去入场，保留回应/退出——JS 反馈属入场类，一并静止）
 *   - html[data-dashboard-style] 为 millennium / future-retro（官方风格让位）
 *   - html.no-animations（官方「禁用动画」开关）
 *   - Edge 浏览器（官方已知 View Transitions 显示异常，跟随官方回退）
 *
 * 安全边界：不改 React 管理的 DOM 结构（文案替换只动文本节点并按时还原；
 * 删行补位只读几何 + WAAPI transform；toast 克隆体 aria-hidden + data-ef-ghost 不进读屏、
 * 不被本层二次识别）。
 */
(function () {
  'use strict';

  var html = document.documentElement;
  var MECH = 'cubic-bezier(0.7, 0, 0.2, 1)';
  var SNAP = 'cubic-bezier(0.16, 1, 0.3, 1)';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var EDGE = /\bEdg(?:e|A|iOS)?\//.test(navigator.userAgent);

  function yielded() {
    var s = html.dataset.dashboardStyle;
    return s === 'millennium' || s === 'future-retro';
  }
  function still() {
    return reduced.matches || html.dataset.efMotion === 'calm' ||
      yielded() || html.classList.contains('no-animations');
  }
  function canReveal() {
    return !still() && !EDGE && typeof document.startViewTransition === 'function';
  }

  /* ---------- 1. 完成黄穿按钮 ---------- */

  /* 找按钮里最后一个非空文本节点（「保存」按钮 = svg + 文本节点）。
     只动文本节点，svg 图标与 React 结构不受影响。 */
  function lastTextNode(el) {
    var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    var last = null;
    while (walker.nextNode()) {
      if (walker.currentNode.data.trim()) last = walker.currentNode;
    }
    return last;
  }

  function flashDone(btn) {
    if (still() || !btn || btn.dataset.efDone === '1') return;
    btn.dataset.efDone = '1';
    btn.classList.remove('ef-is-done');
    void btn.offsetWidth; /* 重启动画 */
    btn.classList.add('ef-is-done');
    setTimeout(function () {
      btn.classList.remove('ef-is-done');
      delete btn.dataset.efDone;
    }, 650);
    var node = lastTextNode(btn);
    if (node && /保存/.test(node.data) && !/已保存/.test(node.data)) {
      var was = node.data;
      node.data = was.replace('保存', '已保存');
      setTimeout(function () {
        if (node.isConnected && node.data !== was) node.data = was;
      }, 1200);
    }
  }

  /* 保存成功信号 = 非 destructive 的「配置已保存」提示条出现。
     此时 handleSave 的 finally 已把 saving 置回 false，按钮已重渲染为稳定态。 */
  function onSaveToast(toast) {
    if (toast.classList.contains('destructive')) return;
    var title = toast.querySelector('[data-dashboard-toast-title="true"]');
    if (!title || title.textContent.indexOf('配置已保存') < 0) return;
    var btns = document.querySelectorAll('button.dashboard-button--default');
    for (var i = 0; i < btns.length; i++) {
      if (/保存/.test(btns[i].textContent) && !btns[i].disabled) flashDone(btns[i]);
    }
  }

  /* ---------- 2. 提示条卸载兜底：克隆擦出 ---------- */

  /* Radix 受控 toast 关闭时直接卸载，data-state='closed' 的 CSS 擦出经常来不及播。
     这里在节点被移除的瞬间克隆一份（aria-hidden + data-ef-ghost，不进读屏、
     不被本层二次识别），原位补完 160ms 擦出。
     若节点带着 closed 状态离开（CSS 已在播），不重复克隆。 */
  function ghostWipeOut(node) {
    if (still()) return;
    var parent = node.parentNode;
    if (!parent || node.dataset.state === 'closed') return;
    var rect = node.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    var ghost = node.cloneNode(true);
    ghost.removeAttribute('id');
    ghost.setAttribute('aria-hidden', 'true');
    ghost.dataset.efGhost = '1';
    ghost.style.cssText = 'position:fixed;margin:0;pointer-events:none;z-index:99;' +
      'left:' + rect.left + 'px;top:' + rect.top + 'px;' +
      'width:' + rect.width + 'px;height:' + rect.height + 'px;';
    document.body.appendChild(ghost);
    var anim = ghost.animate(
      [{ clipPath: 'inset(0 -2% 0 0)' }, { clipPath: 'inset(0 0 0 100%)' }],
      { duration: 160, easing: MECH, fill: 'forwards' }
    );
    anim.onfinish = function () { ghost.remove(); };
    setTimeout(function () { if (ghost.isConnected) ghost.remove(); }, 400);
  }

  /* ---------- 3. 删行：下方行 FLIP 补位 ---------- */

  /* React 删行是同步移除，MutationObserver 回调运行时布局已重算，
     兄弟行几何读出来已是新值——所以几何必须在删除前冻结。
     方案：pointerdown 捕获阶段，若点击落在表格行内（删除按钮所在行），
     冻结该行所有后续兄弟行的 top；删除发生后（childList 移除 TR）
     用冻结值做 FLIP：translateY(旧-新) → none，200ms snap。
     键盘激活删除按钮时 pointerdown 不触发——补 keydown(Enter/Space) 冻结。
     全程只读几何 + WAAPI transform，不碰 React 的 DOM 结构。 */
  var frozenRows = null; /* {tbody, rows: [[el, top], ...]} */

  function freezeFromRow(row) {
    if (still() || !row || !row.parentNode) return;
    var siblings = [];
    for (var n = row.nextElementSibling; n; n = n.nextElementSibling) {
      siblings.push([n, n.getBoundingClientRect().top]);
    }
    frozenRows = siblings.length ? { tbody: row.parentNode, rows: siblings } : null;
  }

  function rowOf(el) {
    var tr = el.closest && el.closest('tr');
    if (!tr) return null;
    var p = tr.parentNode;
    return (p && (p.tagName === 'TBODY' || p.tagName === 'TABLE')) ? tr : null;
  }

  document.addEventListener('pointerdown', function (e) {
    var tr = e.target && rowOf(e.target);
    if (tr) freezeFromRow(tr);
  }, { capture: true, passive: true });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var tr = e.target && rowOf(e.target);
    if (tr) freezeFromRow(tr);
  }, { capture: true });

  function flipFrozen(tbody) {
    if (!frozenRows || frozenRows.tbody !== tbody) return;
    var rows = frozenRows.rows;
    frozenRows = null;
    if (still()) return;
    requestAnimationFrame(function () {
      for (var i = 0; i < rows.length; i++) {
        var el = rows[i][0], oldTop = rows[i][1];
        if (!el.isConnected) continue;
        var dy = oldTop - el.getBoundingClientRect().top;
        if (dy > 0.5) {
          el.animate(
            [{ transform: 'translateY(' + dy + 'px)' }, { transform: 'none' }],
            { duration: 200, easing: SNAP }
          );
        }
      }
    });
  }

  /* ---------- 4. 深浅切换揭幕（统一接管） ---------- */

  /* 三个入口：
     a. 侧边栏按钮（ObservationSidebar）：aria-label「切换到浅色/深色模式」等四语，
        官方自带 startViewTransition(500ms ease-in-out)——本层拦下原 click，
        用自己的 420ms MECH 替代（软曲线违反机械语法）。
     b. 外观页 SegmentedControl（aria-label「主题模式」等四语）：官方裸切，补揭幕。
     c. auth 页按钮：aria-label 同 a，官方裸切，补揭幕。
     实现：click 捕获阶段拦下原事件 → startViewTransition 回调里派发替代 click
     → React 状态更新落在快照窗口内。替代 click 带 efReveal 标记，放行不二次拦截。
     静止/Edge/无 API 时放行原生流程（侧边栏回官方过渡，其余裸切）。 */

  function revealWrap(x, y, apply) {
    var r = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    html.classList.add('ef-theming');
    var t;
    try {
      t = document.startViewTransition(apply);
    } catch (e) {
      html.classList.remove('ef-theming');
      apply();
      return;
    }
    t.ready.then(function () {
      html.animate(
        { clipPath: ['circle(0px at ' + x + 'px ' + y + 'px)', 'circle(' + r + 'px at ' + x + 'px ' + y + 'px)'] },
        { duration: 420, easing: MECH, pseudoElement: '::view-transition-new(root)' }
      );
    }).catch(function () {});
    t.finished.finally(function () {
      html.classList.remove('ef-theming');
    });
  }

  /* 深浅切换按钮：aria-label 四语（header 与 auth 共用同一组文案） */
  var THEME_BTN_LABEL = /切换到(浅色|深色)模式|switch to (light|dark) mode|(ライト|ダーク)モードに切り替える|(라이트|다크) 모드로 전환/i;
  /* 主题模式分段控件：aria-label 四语 */
  var THEME_MODE_LABEL = /主题模式|theme\s*mode|テーマモード|테마\s*모드/i;

  function themeToggleOf(target) {
    if (!target || !target.closest) return null;
    /* a/c：独立按钮（侧边栏 / auth） */
    var btn = target.closest('button[aria-label]');
    if (btn && THEME_BTN_LABEL.test(btn.getAttribute('aria-label') || '')) {
      return { el: btn, kind: 'toggle' };
    }
    /* b：外观页分段控件里的选项按钮 */
    var item = target.closest('[data-dashboard-segmented-control="true"] button');
    if (item) {
      var group = item.closest('[data-dashboard-segmented-control="true"]');
      var label = (group && group.getAttribute('aria-label')) || '';
      if (THEME_MODE_LABEL.test(label)) return { el: item, kind: 'segment' };
    }
    return null;
  }

  document.addEventListener('click', function (e) {
    var hit = themeToggleOf(e.target);
    if (!hit) return;
    var item = hit.el;
    if (item.dataset.efReveal === '1') return; /* 替代 click，放行给 React */
    if (hit.kind === 'segment') {
      /* 已选中的项再点不会翻转，无需过渡。
         SegmentedControl 的 Button 带 aria-pressed；radix RadioGroup.Item
         asChild 会把 data-state / aria-checked 合并到同一 button 上。 */
      if (item.getAttribute('aria-pressed') === 'true' ||
          item.getAttribute('aria-checked') === 'true' ||
          item.dataset.state === 'checked') return;
    }
    if (!canReveal()) return; /* 静止/Edge/无 API：放行原生流程 */
    var x = e.clientX, y = e.clientY;
    if (!x && !y) { /* 键盘激活：从控件中心展开 */
      var box = item.getBoundingClientRect();
      x = box.left + box.width / 2;
      y = box.top + box.height / 2;
    }
    item.dataset.efReveal = '1';
    setTimeout(function () { delete item.dataset.efReveal; }, 600);
    e.stopPropagation(); /* 原事件不进 React（root 监听器收不到） */
    e.preventDefault();
    revealWrap(x, y, function () {
      item.dispatchEvent(new MouseEvent('click', {
        bubbles: true, cancelable: true, clientX: x, clientY: y
      }));
    });
  }, { capture: true });

  /* ---------- 总观察器：toast / 删行 ---------- */

  var bodyMO = new MutationObserver(function (muts) {
    for (var i = 0; i < muts.length; i++) {
      var m = muts[i];
      var added = m.addedNodes, removed = m.removedNodes;
      for (var j = 0; j < added.length; j++) {
        var a = added[j];
        if (a.nodeType !== 1 || a.dataset.efGhost === '1') continue;
        if (a.matches && a.matches('[data-dashboard-toast="true"]')) onSaveToast(a);
        else if (a.querySelectorAll) {
          var ts = a.querySelectorAll('[data-dashboard-toast="true"]:not([data-ef-ghost])');
          for (var k = 0; k < ts.length; k++) onSaveToast(ts[k]);
        }
      }
      for (var j2 = 0; j2 < removed.length; j2++) {
        var r = removed[j2];
        if (r.nodeType !== 1 || r.dataset.efGhost === '1') continue;
        if (r.matches && r.matches('[data-dashboard-toast="true"]')) {
          ghostWipeOut(r);
        } else if (r.tagName === 'TR' && r.parentNode &&
                   (r.parentNode.tagName === 'TBODY' || r.parentNode.tagName === 'TABLE')) {
          flipFrozen(r.parentNode);
        }
      }
    }
  });

  function start() {
    bodyMO.observe(document.body, { childList: true, subtree: true });
  }
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start);

  /* 卸载钩子：整页刷新前断开观察器，避免幽灵回调 */
  window.addEventListener('pagehide', function () {
    bodyMO.disconnect();
  });
})();