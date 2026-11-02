import { useEffect, useRef } from "react";

/** Decorative browser-only feedback: no React updates or service calls on pointer movement. */
export function PointerFeedback() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const fine = window.matchMedia("(hover: hover) and (pointer: fine)");
    const cells = new Map<string, { x: number; y: number; at: number; strength: number }>();
    let frame = 0;
    let color = "";
    const size = 36;
    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = window.innerWidth * ratio;
      canvas.height = window.innerHeight * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      color = getComputedStyle(canvas).getPropertyValue("--grid-ink").trim();
      cells.clear();
    };
    const clear = () => {
      cells.clear();
      context.clearRect(0, 0, window.innerWidth, window.innerHeight);
      window.cancelAnimationFrame(frame);
      frame = 0;
    };
    const paint = (now: number) => {
      frame = 0;
      context.clearRect(0, 0, window.innerWidth, window.innerHeight);
      for (const [key, cell] of cells) {
        const remaining = 1 - (now - cell.at) / 850;
        const target = document.elementFromPoint(cell.x + size / 2, cell.y + size / 2);
        // Only paint exposed background, never a report, toolbar, data tile or text.
        if (remaining <= 0 || !target?.matches(".page-layout, main.bg-canvas")) {
          cells.delete(key);
          continue;
        }
        context.globalAlpha = remaining * remaining * cell.strength;
        context.fillStyle = color;
        context.fillRect(cell.x + 2, cell.y + 2, size - 4, size - 4);
        context.globalAlpha = remaining * 0.2;
        context.strokeStyle = color;
        context.strokeRect(cell.x + 2.5, cell.y + 2.5, size - 5, size - 5);
      }
      if (cells.size) frame = window.requestAnimationFrame(paint);
    };
    const move = (event: PointerEvent) => {
      if (motion.matches || !fine.matches || event.pointerType === "touch") return;
      const target = event.target;
      if (!(target instanceof Element) || !target.matches(".page-layout, main.bg-canvas")) return;
      const x = Math.floor(event.clientX / size) * size;
      const y = Math.floor(event.clientY / size) * size;
      const now = performance.now();
      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          const cx = x + dx * size;
          const cy = y + dy * size;
          cells.set(`${cx}:${cy}`, {
            x: cx,
            y: cy,
            at: now,
            strength: dx === 0 && dy === 0 ? 0.23 : 0.07,
          });
        }
      }
      if (!frame) frame = window.requestAnimationFrame(paint);
    };
    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("scroll", clear, true);
    window.addEventListener("blur", clear);
    document.addEventListener("pointermove", move, { passive: true });
    motion.addEventListener("change", clear);
    return () => {
      clear();
      window.removeEventListener("resize", resize);
      window.removeEventListener("scroll", clear, true);
      window.removeEventListener("blur", clear);
      document.removeEventListener("pointermove", move);
      motion.removeEventListener("change", clear);
    };
  }, []);

  useEffect(() => {
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    let frame = 0;
    let surface: HTMLElement | null = null;
    let pointerX = 0;

    const clear = () => {
      surface?.removeAttribute("data-pointer-active");
      surface = null;
    };
    const move = (event: PointerEvent) => {
      if (motion.matches || !finePointer.matches || event.pointerType === "touch") return;
      const target = event.target;
      const next =
        target instanceof Element ? target.closest<HTMLElement>("[data-pointer-surface]") : null;
      if (next !== surface) {
        clear();
        surface = next;
      }
      if (!surface) return;
      pointerX = event.clientX;
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        if (!surface) return;
        const bounds = surface.getBoundingClientRect();
        surface.style.setProperty("--pointer-x", `${pointerX - bounds.left}px`);
        surface.setAttribute("data-pointer-active", "");
      });
    };

    document.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", clear);
    window.addEventListener("blur", clear);
    motion.addEventListener("change", clear);
    return () => {
      window.cancelAnimationFrame(frame);
      clear();
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", clear);
      window.removeEventListener("blur", clear);
      motion.removeEventListener("change", clear);
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden="true" className="pointer-grid" />;
}
