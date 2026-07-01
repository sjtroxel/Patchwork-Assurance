// Patchwork Assurance landing page — motion (Phase 4.5 · M3c/M3d).
// (1) Scroll-reveal: elements marked .reveal fade/rise in as they enter view.
// (2) Video play/pause: background videos play only while on screen, so two
//     clips never decode at once (battery/CPU) and the offscreen closing video
//     (preload=none) loads lazily on first view.
// Both are progressive enhancements: with no IntersectionObserver or with
// prefers-reduced-motion, content is shown and no video is driven.
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var hasIO = "IntersectionObserver" in window;

  // (1) scroll-reveal
  var els = document.querySelectorAll(".reveal");
  if (els.length) {
    if (reduceMotion || !hasIO) {
      els.forEach(function (el) { el.classList.add("is-visible"); });
    } else {
      var revealObserver = new IntersectionObserver(
        function (entries, obs) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              obs.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15, rootMargin: "0px 0px -10% 0px" }
      );
      els.forEach(function (el) { revealObserver.observe(el); });
    }
  }

  // (2) play/pause background videos by visibility (skipped under reduced motion,
  // where CSS hides the videos and shows the still poster instead)
  var videos = document.querySelectorAll(".bg-video");
  if (videos.length && hasIO && !reduceMotion) {
    var videoObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          var v = entry.target;
          if (entry.isIntersecting) {
            var p = v.play();
            if (p && p.catch) p.catch(function () {});
          } else {
            v.pause();
          }
        });
      },
      { threshold: 0.1 }
    );
    videos.forEach(function (v) { videoObserver.observe(v); });
  }
})();

// (3) Theme toggle (Phase 11.1) — light/dark, persisted in localStorage. Default follows the OS
// (prefers-color-scheme), so the landing and the Streamlit app (on its Auto setting) move together
// with the system theme. A no-flash inline script in <head> sets data-theme before paint; this just
// wires the button + tracks live OS changes when the user hasn't made an explicit choice.
(function () {
  "use strict";
  var root = document.documentElement;
  var btn = document.querySelector(".theme-toggle");
  var mq = window.matchMedia("(prefers-color-scheme: dark)");

  function effective() {
    return root.getAttribute("data-theme") || (mq.matches ? "dark" : "light");
  }
  function apply(mode) {
    root.setAttribute("data-theme", mode);
    if (btn) {
      // show the icon for the mode you'd switch TO: sun when dark, moon when light
      btn.innerHTML = mode === "dark" ? "&#9728;" : "&#9790;";
      btn.setAttribute("aria-label", mode === "dark" ? "Switch to light mode" : "Switch to dark mode");
    }
  }

  apply(effective());
  if (btn) {
    btn.addEventListener("click", function () {
      var next = effective() === "dark" ? "light" : "dark";
      try { localStorage.setItem("pa-theme", next); } catch (e) {}
      apply(next);
    });
  }
  // Follow live OS changes only while the user hasn't chosen explicitly (mirrors the app on Auto).
  mq.addEventListener("change", function (e) {
    try { if (!localStorage.getItem("pa-theme")) apply(e.matches ? "dark" : "light"); } catch (err) {}
  });
})();
