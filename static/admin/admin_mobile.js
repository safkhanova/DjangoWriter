/* Phone-friendly admin tables (CSS in site_admin.css, active below 768px / 1024px).
   Unfold hides table headers on small screens, so every cell gets its column name
   in data-label, which the CSS shows next to (change lists) or above (tabular
   inlines) the value. */
(function () {
  "use strict";

  function text(el) {
    return (el.textContent || "").replace(/\s+/g, " ").trim();
  }

  // Header text without the sorting icons (material-symbols ligatures).
  function headerLabel(th) {
    const copy = th.cloneNode(true);
    copy.querySelectorAll(".material-symbols-outlined, .sortoptions").forEach((n) => n.remove());
    return text(copy);
  }

  function labelChangeList() {
    const table = document.getElementById("result_list");
    if (!table) return;
    const labels = [...table.querySelectorAll("thead th")].map(headerLabel);
    // drag and drop is unreliable on touch screens: phones get the order number field instead
    const orderField = table.dataset.orderingField;
    if (orderField) {
      table.querySelectorAll(`tr.data-row > td.field-${orderField}`).forEach((td) => {
        // Unfold's layered "!hidden" cannot be overridden from CSS; sa-order-cell hides it on desktop instead
        td.classList.remove("!hidden");
        td.classList.add("sa-order-cell");
      });
    }
    table.querySelectorAll("tr.data-row").forEach((row) => {
      [...row.children].forEach((cell, i) => {
        if (labels[i]) cell.dataset.label = labels[i];
        const empty = !text(cell) && !cell.querySelector("input, select, textarea, img, svg, a, button");
        cell.classList.toggle("sa-empty-cell", empty);
      });
    });
  }

  function labelTabularInlines(root) {
    (root || document).querySelectorAll("table.formset").forEach((table) => {
      const labels = {};
      table.querySelectorAll("thead th").forEach((th) => {
        const col = [...th.classList].find((c) => c.startsWith("column-"));
        if (col) labels[col.slice(7)] = headerLabel(th);
      });
      table.querySelectorAll("td.field-tabular").forEach((td) => {
        const field = [...td.classList].find((c) => c.startsWith("field-") && c !== "field-tabular");
        const label = field && labels[field.slice(6)];
        if (label) td.dataset.label = label;
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    labelChangeList();
    labelTabularInlines();
  });
  // rows added with "add another" in a tabular inline
  document.addEventListener("formset:added", () => labelTabularInlines());
})();
