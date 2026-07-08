"use client";

import { useEffect } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

/**
 * Scroll-driven cinematic effects for the landing, layered on top of Lenis:
 * the hero content parallax-exits and dims while the field drifts at a different
 * depth, section labels slide in, and the write-back card rises into place. All
 * scrubbed to scroll. Reduced-motion users get a static page.
 */
export default function CinematicScroll() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      // hero content parallax exit
      gsap.to("[data-hero-content]", {
        yPercent: -22,
        opacity: 0.08,
        ease: "none",
        scrollTrigger: { trigger: "[data-hero]", start: "top top", end: "bottom top", scrub: true },
      });
      // the field drifts down slightly (parallax depth) as the hero leaves
      gsap.to("[data-hero-field]", {
        yPercent: 14,
        ease: "none",
        scrollTrigger: { trigger: "[data-hero]", start: "top top", end: "bottom top", scrub: true },
      });
      // section labels slide in from the left as they enter
      gsap.utils.toArray<HTMLElement>("[data-slide]").forEach((el) => {
        gsap.from(el, {
          x: -28,
          opacity: 0,
          duration: 0.8,
          ease: "power3.out",
          scrollTrigger: { trigger: el, start: "top 88%" },
        });
      });
      // the write-back card rises and settles
      const card = document.querySelector("[data-writeback-card]");
      if (card) {
        gsap.from(card, {
          y: 60,
          opacity: 0,
          scale: 0.96,
          duration: 1,
          ease: "power3.out",
          scrollTrigger: { trigger: card, start: "top 82%" },
        });
      }
    });

    // recalc once fonts/layout settle
    const t = setTimeout(() => ScrollTrigger.refresh(), 300);
    return () => {
      clearTimeout(t);
      ctx.revert();
    };
  }, []);

  return null;
}
