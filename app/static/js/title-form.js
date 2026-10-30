// Adapt the form to the chosen type. Each kind has its own statuses, status labels,
// genres and extra fields (seasons for series and anime; completion and hours for
// games; author and pages for books).
// The server renders the right initial state; this keeps it in sync on change.
(() => {
  const form = document.querySelector(".title-form");
  if (!form) return;

  const config = JSON.parse(document.getElementById("kind-config").textContent);
  const genreSelect = form.querySelector("#genre");

  function checkedValue(name) {
    const input = form.querySelector(`input[name="${name}"]:checked`);
    return input ? input.value : "";
  }

  function updateGenres(kind) {
    const current = genreSelect.value;
    const genres = config[kind].genres;
    genreSelect.replaceChildren(new Option("Choose a genre…", ""), ...genres.map((g) => new Option(g, g)));
    // Keep the chosen genre if the new kind has it too (e.g. "Action").
    genreSelect.value = genres.includes(current) ? current : "";
  }

  function update(kindChanged) {
    const kind = checkedValue("kind");
    const labels = config[kind].statuses; // {status value: label}, only the statuses this kind allows

    // A status the new kind doesn't have (e.g. a movie can't be "Dropped") falls back to the first one.
    if (!(checkedValue("status") in labels)) {
      form.querySelector(`input[name="status"][value="${Object.keys(labels)[0]}"]`).checked = true;
    }
    form.querySelectorAll("[data-status-label]").forEach((el) => {
      const label = labels[el.dataset.statusLabel];
      if (label) el.textContent = label;
    });

    const status = checkedValue("status");
    form.querySelectorAll("[data-kinds], [data-statuses]").forEach((el) => {
      const kindOk = !el.dataset.kinds || el.dataset.kinds.split(" ").includes(kind);
      const statusOk = !el.dataset.statuses || el.dataset.statuses.split(" ").includes(status);
      el.hidden = !(kindOk && statusOk);
    });
    // "Watched on", "Completed on", "Dropped on"…
    const ended = status === "dropped" ? status : "watched";
    form.querySelector("[data-finished-label]").textContent = `${labels[ended] || "Finished"} on`;

    if (kindChanged) {
      updateGenres(kind);
      form.querySelector("[data-year-label]").textContent = config[kind].year_label;
      form.querySelector("[data-platform-label]").textContent = config[kind].platform_label;
      form.querySelector("#platform-options").replaceChildren(...config[kind].platforms.map((p) => new Option(p)));
    }
  }

  // Editing a title and moving it on (started it, finished it): the date is today unless you change it.
  // New titles are often things from the past, so their dates are left for you to fill in.
  function suggestToday(status) {
    if (!("editing" in form.dataset)) return;
    const field = { watching: "#started_on", watched: "#finished_on", dropped: "#finished_on" }[status];
    const input = field && form.querySelector(field);
    if (input && !input.value) input.value = form.dataset.today;
  }

  form.addEventListener("change", (event) => {
    if (event.target.name === "kind") update(true);
    else if (event.target.name === "status") {
      update(false);
      suggestToday(event.target.value);
    }
  });

  // One "episodes" input per season, so seasons can have different lengths.
  const seasonCount = form.querySelector("#season_count");
  const seasonRows = form.querySelector("#season-rows");

  function syncSeasonRows() {
    const wanted = parseInt(seasonCount.value, 10);
    // Ignore empty or out-of-range values while the user is still typing.
    if (!(wanted >= 1 && wanted <= 50)) return;

    while (seasonRows.children.length < wanted) {
      const last = seasonRows.lastElementChild;
      const row = last.cloneNode(true);
      row.querySelector(".season-row-name").textContent = `Season ${seasonRows.children.length + 1}`;
      // Most seasons are as long as the one before, so start from that count.
      row.querySelector("input").value = last.querySelector("input").value;
      seasonRows.append(row);
    }
    while (seasonRows.children.length > wanted) {
      seasonRows.lastElementChild.remove();
    }
  }

  seasonCount.addEventListener("input", syncSeasonRows);
})();
