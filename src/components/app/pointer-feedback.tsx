import { useEffect } from "react";

/** Decorative browser-only feedback: no React updates or service calls on pointer movement. */
export function PointerFeedback() {
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

  return null;
}
