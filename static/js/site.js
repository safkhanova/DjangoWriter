/* Public site: mobile menu, archive filter pills, YouTube click-to-load. No dependencies. */
(function () {
  "use strict";

  // Mobile navigation
  const toggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav]");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      const open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) nav.classList.remove("is-open");
    });
  }

  // Homepage archive filter: «Hamısı / Qəzet / Televiziya»
  document.querySelectorAll("[data-filter-group]").forEach(function (group) {
    const table = document.querySelector('[data-filter-target="' + group.dataset.filterGroup + '"]');
    if (!table) return;
    group.addEventListener("click", function (e) {
      const btn = e.target.closest("[data-filter]");
      if (!btn) return;
      group.querySelectorAll(".pill").forEach((p) => p.classList.toggle("is-active", p === btn));
      table.querySelectorAll("tbody tr").forEach(function (row) {
        row.hidden = !!btn.dataset.filter && row.dataset.category !== btn.dataset.filter;
      });
    });
  });

  // YouTube: load the player only on click (faster page, no tracking before consent)
  document.addEventListener("click", function (e) {
    const box = e.target.closest(".yt-lite");
    if (!box || box.querySelector("iframe")) return;
    const iframe = document.createElement("iframe");
    iframe.src = "https://www.youtube-nocookie.com/embed/" + encodeURIComponent(box.dataset.yt) + "?autoplay=1&rel=0";
    iframe.title = box.dataset.title || "YouTube video";
    iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
    iframe.allowFullscreen = true;
    box.appendChild(iframe);
  });
})();
