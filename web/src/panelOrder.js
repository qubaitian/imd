import { tick } from "svelte";

export async function keepPanelState(node, update) {
  const scroll = [...node.querySelectorAll(".document-scroll, .cm-scroller, .xterm-viewport")]
    .map((element) => ({ element, top: element.scrollTop, left: element.scrollLeft }));
  const focused = node.contains(document.activeElement) ? document.activeElement : null;
  update();
  await tick();
  if (focused?.isConnected && document.activeElement !== focused) focused.focus({ preventScroll: true });
  for (const { element, top, left } of scroll) {
    if (element.isConnected) element.scrollTo({ top, left, behavior: "instant" });
  }
}

// Move existing panels only after the pointer drops them.  
export function panelOrder(node, options) {
  let drag = null;
  const marker = document.createElement("div");
  marker.className = "panel-insertion";
  marker.setAttribute("aria-hidden", "true");

  function clear() {
    if (!drag) return;
    const { panel, pointerId } = drag;
    drag = null;
    marker.remove();
    panel.classList.remove("panel-dragging");
    node.classList.remove("panel-sorting");
    if (node.hasPointerCapture(pointerId)) node.releasePointerCapture(pointerId);
  }

  function down(event) {
    if (options.disabled || drag || event.button !== 0 || !event.isPrimary) return;
    const header = event.target.closest(".topbar");
    const panel = header?.closest("[data-panel-id]");
    if (!panel || panel.parentElement !== node) return;
    if (event.target.closest("button, a, input, textarea, select, [contenteditable]")) return;
    const panels = [...node.children].filter((child) => child.hasAttribute("data-panel-id"));
    if (panels.length < 2) return;
    event.preventDefault();
    drag = {
      panel, panels, pointerId: event.pointerId,
      startX: event.clientX, startY: event.clientY,
      index: panels.indexOf(panel), target: panels.indexOf(panel), active: false,
    };
    node.setPointerCapture(event.pointerId);
  }

  function move(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    if (!drag.active && Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) < 5) return;
    drag.active = true;
    drag.panel.classList.add("panel-dragging");
    node.classList.add("panel-sorting");
    const bounds = node.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) {
      drag.target = drag.index;
      marker.remove();
      return;
    }
    const others = drag.panels.filter((panel) => panel !== drag.panel);
    let index = others.findIndex((panel) => {
      const rect = panel.getBoundingClientRect();
      return event.clientX < rect.left + rect.width / 2;
    });
    if (index < 0) index = others.length;
    drag.target = index;
    if (index === drag.index) {
      marker.remove();
      return;
    }
    const edge = index < others.length
      ? others[index].getBoundingClientRect().left
      : others.at(-1).getBoundingClientRect().right;
    marker.style.left = `${Math.max(bounds.left + 2, Math.min(bounds.right - 2, edge))}px`;
    marker.style.top = `${bounds.top}px`;
    marker.style.height = `${bounds.height}px`;
    node.append(marker);
  }

  function up(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    move(event);
    const { panel, target, index, active } = drag;
    clear();
    if (active && target !== index) options.onMove(panel.dataset.panelId, target);
  }

  function keydown(event) {
    if (event.key === "Escape" && drag) {
      event.preventDefault();
      clear();
    }
  }

  node.addEventListener("pointerdown", down);
  node.addEventListener("pointermove", move);
  node.addEventListener("pointerup", up);
  node.addEventListener("pointercancel", clear);
  node.addEventListener("lostpointercapture", clear);
  window.addEventListener("keydown", keydown, true);
  window.addEventListener("blur", clear);
  return {
    update(next) {
      options = next;
      if (options.disabled) clear();
    },
    destroy() {
      clear();
      node.removeEventListener("pointerdown", down);
      node.removeEventListener("pointermove", move);
      node.removeEventListener("pointerup", up);
      node.removeEventListener("pointercancel", clear);
      node.removeEventListener("lostpointercapture", clear);
      window.removeEventListener("keydown", keydown, true);
      window.removeEventListener("blur", clear);
    },
  };
}
