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
