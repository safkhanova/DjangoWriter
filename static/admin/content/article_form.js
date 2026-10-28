/* Article admin: «Növ» lists only the types of the selected «Bölmə».
   Data: ArticleAdmin.changeform_view -> categories_by_section (json_script). */
(function () {
  "use strict";

  function init() {
    const dataEl = document.getElementById("categories-by-section");
    const section = document.getElementById("id_section");
    const category = document.getElementById("id_category");
    if (!dataEl || !section || !category) return;
    const bySection = JSON.parse(dataEl.textContent);

    function fill() {
      const current = category.value;
      const choices = bySection[section.value] || [];
      category.innerHTML = "";
      const empty = new Option(
        !section.value ? "Əvvəlcə bölməni seçin" : choices.length ? "Seçin" : "Bu bölmədə növ yoxdur", ""
      );
      category.add(empty);
      choices.forEach(function ([id, name]) {
        category.add(new Option(name, id, false, String(id) === current));
      });
      category.disabled = !section.value || !choices.length;
      category.dispatchEvent(new Event("change", { bubbles: true }));
    }

    section.addEventListener("change", fill);
    fill();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
