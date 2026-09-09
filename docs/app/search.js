// Global search across fields, equity legal entities, and current
// operators (spec: equity frontend checkpoint, closing the Phase 1
// closeout audit's "field search still unfinished" note). Deterministic,
// case-insensitive substring matching only - never fuzzy, never merging
// entity types without a label, matching this whole project's stance on
// name matching (spec section 15.5).

const RESULT_TYPE_LABELS = {
  field: "Field",
  "legal-entity": "Legal entity",
  operator: "Operator",
};

export function buildSearchIndex({ fields, legalEntities, operators }) {
  const index = [];
  for (const f of fields) {
    index.push({ type: "field", label: f.name, slug: f.slug });
  }
  for (const e of legalEntities) {
    index.push({ type: "legal-entity", label: e.name, slug: e.slug });
  }
  for (const op of operators) {
    index.push({ type: "operator", label: op, slug: op });
  }
  return index;
}

export function runSearch(index, query, limit = 20) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return index.filter((entry) => entry.label.toLowerCase().includes(q)).slice(0, limit);
}

export function resultTypeLabel(type) {
  return RESULT_TYPE_LABELS[type] || type;
}

// Attaches a keyboard-accessible combobox: text input + a listbox of
// results, each labelled with its result type. `onSelect(entry)` is
// called when a result is chosen (click, Enter, or nothing else).
export function attachSearchUI(inputEl, listEl, index, onSelect) {
  let activeIndex = -1;
  let results = [];

  function render() {
    listEl.innerHTML = "";
    results.forEach((entry, i) => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.id = `search-result-${i}`;
      li.setAttribute("aria-selected", String(i === activeIndex));
      li.className = "search-result" + (i === activeIndex ? " search-result-active" : "");
      li.innerHTML = `<span class="search-result-type">${resultTypeLabel(entry.type)}</span> ${entry.label.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]))}`;
      li.addEventListener("mousedown", (e) => {
        e.preventDefault();
        onSelect(entry);
        close();
      });
      listEl.appendChild(li);
    });
    listEl.hidden = results.length === 0;
    inputEl.setAttribute("aria-expanded", String(results.length > 0));
    inputEl.setAttribute("aria-activedescendant", activeIndex >= 0 ? `search-result-${activeIndex}` : "");
  }

  function close() {
    results = [];
    activeIndex = -1;
    listEl.hidden = true;
    inputEl.setAttribute("aria-expanded", "false");
  }

  inputEl.addEventListener("input", () => {
    results = runSearch(index, inputEl.value);
    activeIndex = results.length > 0 ? 0 : -1;
    render();
  });

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (results.length === 0) return;
      activeIndex = (activeIndex + 1) % results.length;
      render();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (results.length === 0) return;
      activeIndex = (activeIndex - 1 + results.length) % results.length;
      render();
    } else if (e.key === "Enter") {
      if (activeIndex >= 0 && results[activeIndex]) {
        e.preventDefault();
        onSelect(results[activeIndex]);
        close();
      }
    } else if (e.key === "Escape") {
      close();
    }
  });

  inputEl.addEventListener("blur", () => {
    // Delay so a mousedown-triggered selection on the listbox still fires
    // before the list is hidden.
    setTimeout(close, 150);
  });
}
