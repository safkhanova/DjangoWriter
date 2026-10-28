/* Article admin: in each content block show only the fields its type uses.
   The type -> fields map comes from ArticleBlock.FIELDS_BY_TYPE (json_script). */
(function () {
  "use strict";
  const ALWAYS = ["type", "is_visible", "order", "id", "article", "DELETE"];

  function fieldMap() {
    const el = document.getElementById("block-fields-map");
    return el ? JSON.parse(el.textContent) : null;
  }

  function apply(select, map) {
    const form = select.closest(".form-group");
    if (!form) return;
    const wanted = new Set([...(map[select.value] || []), ...ALWAYS]);
    // Only touch wrappers named after a real block field (Unfold also uses
    // classes like "field-row" / "field-line" for layout containers).
    const known = new Set([].concat(...Object.values(map), ALWAYS));
    form.querySelectorAll("[class*='field-']").forEach(function (el) {
      const name = Array.from(el.classList)
        .filter((c) => c.startsWith("field-"))
        .map((c) => c.slice(6))
        .find((n) => known.has(n));
      if (name) el.classList.toggle("sa-hidden-field", !wanted.has(name));
    });
    // Hide layout rows left with no visible field (no empty bordered strips).
    form.querySelectorAll(".field-row").forEach(function (row) {
      row.classList.toggle("sa-hidden-field", !row.querySelector(".field-line:not(.sa-hidden-field)"));
    });
  }

  function init() {
    const map = fieldMap();
    if (!map) return;
    const isTypeSelect = (el) => el && el.matches && el.matches("select[name^='blocks-'][name$='-type']");
    document.querySelectorAll("select[name^='blocks-'][name$='-type']").forEach((s) => apply(s, map));
    document.addEventListener("change", function (e) { if (isTypeSelect(e.target)) apply(e.target, map); });
    document.addEventListener("formset:added", function (e) {
      const root = e.target && e.target.querySelector ? e.target : document;
      root.querySelectorAll("select[name$='-type']").forEach((s) => { if (isTypeSelect(s)) apply(s, map); });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
