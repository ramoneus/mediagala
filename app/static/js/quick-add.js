// Quick add: "+ Add title" opens a search under the button. "+ Watchlist" puts a result in the
// fridge with one click (the server fetches its details and cover), "⋯" opens the full form
// filled in, and the panel stays open so you can add several in a row. Closing it shows them.
(() => {
  const panel = document.getElementById("quick-add");
  const opener = document.querySelector("[data-quick-add]");
  if (!panel || !opener) return;

  const sources = JSON.parse(panel.dataset.sources); // {kind: {name, notice, label, planned}}
  const backdrop = document.querySelector(".quick-add-backdrop");
  const query = panel.querySelector("#quick-add-query");
  const list = panel.querySelector(".quick-add-results");
  const status = panel.querySelector(".quick-add-status");
  const manual = panel.querySelector(".quick-add-manual");
  const credit = panel.querySelector(".quick-add-credit");
  const kindButtons = [...panel.querySelectorAll("[data-kind]")];

  const added = []; // ids put in the fridge while the panel was open
  let kind = null;
  let timer = null;
  let pending = null; // the search in flight, so a slower, older answer can't overwrite a newer one

  function say(message) {
    status.textContent = message;
  }

  function lastKind() {
    try {
      return localStorage.getItem("quick-add-kind");
    } catch (e) {
      return null; // storage can be blocked
    }
  }

  function rememberKind(value) {
    try {
      localStorage.setItem("quick-add-kind", value);
    } catch (e) {}
  }

  // On a kind's tab, add that kind; otherwise the kind added last time; otherwise movies.
  function startingKind() {
    const onPage = new URLSearchParams(location.search).get("kind");
    return [onPage, lastKind(), "movie", Object.keys(sources)[0]].find((value) => value in sources);
  }

  function setKind(value) {
    kind = value;
    kindButtons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.kind === value)));
    query.placeholder = `Search ${sources[value].name}…`;
    manual.href = `/titles/new?kind=${value}`;
    credit.textContent = sources[value].notice;
  }

  function open() {
    panel.hidden = false;
    backdrop.hidden = false;
    opener.setAttribute("aria-expanded", "true");
    if (!kind) setKind(startingKind());
    query.focus();
    query.select();
  }

  function close() {
    panel.hidden = true;
    backdrop.hidden = true;
    opener.setAttribute("aria-expanded", "false");
    if (added.length) {
      location.href = `/?added=${added.join(",")}`; // show what went into the fridge
    } else {
      opener.focus();
    }
  }

  // --- Results -----------------------------------------------------------------------

  function link(href, text, className) {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = text;
    a.className = className;
    return a;
  }

  function inFridge(id) {
    return link(`/titles/${id}`, "✓ In your fridge", "qa-done");
  }

  function row(match) {
    const item = document.createElement("li");
    item.className = "qa-row";

    const thumb = document.createElement(match.thumb_url ? "img" : "span");
    thumb.className = "qa-thumb";
    if (match.thumb_url) {
      thumb.src = match.thumb_url;
      thumb.alt = "";
      thumb.loading = "lazy";
    }

    const text = document.createElement("span");
    text.className = "qa-text";
    const name = document.createElement("strong");
    name.textContent = match.title;
    const meta = document.createElement("small");
    meta.textContent = [match.year, match.author, match.genre].filter(Boolean).join(" · ");
    text.append(name, meta);
    item.append(thumb, text);

    if (match.in_collection) {
      item.append(inFridge(match.in_collection));
      return item;
    }

    const add = document.createElement("button");
    add.type = "button";
    add.className = "qa-add";
    add.textContent = `+ ${sources[kind].planned}`;
    add.addEventListener("click", () => quickAdd(match, add));

    const more = link(`/titles/new?kind=${kind}&pick=${encodeURIComponent(match.source_id)}`, "⋯", "qa-more");
    more.title = "Add with details";
    more.setAttribute("aria-label", `Add ${match.title} with details`);

    item.append(add, more);
    return item;
  }

  async function search() {
    const text = query.value.trim();
    if (text.length < 2) {
      list.replaceChildren();
      say("");
      return;
    }
    if (pending) pending.abort();
    pending = new AbortController();
    say(`Searching ${sources[kind].name}…`);
    try {
      const response = await fetch(`/lookup/${kind}?q=${encodeURIComponent(text)}`, { signal: pending.signal });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Something went wrong.");
      list.replaceChildren(...body.results.map(row));
      say(body.results.length ? "" : "Nothing found. Try another spelling, or add it by hand.");
    } catch (error) {
      if (error.name !== "AbortError") {
        list.replaceChildren();
        say(error.message);
      }
    }
  }

  async function quickAdd(match, button) {
    button.disabled = true;
    button.textContent = "Adding…";
    try {
      const response = await fetch(`/lookup/${kind}/${encodeURIComponent(match.source_id)}/add`, { method: "POST" });
      const body = await response.json();
      if (response.status === 201) {
        added.push(body.id);
        rememberKind(kind);
        button.nextElementSibling.remove(); // the "⋯" link
        button.replaceWith(link(`/titles/${body.id}`, "✓ Added", "qa-done"));
        say(`Added ${body.title}. Add more, or close to see ${added.length > 1 ? "them" : "it"} in the fridge.`);
      } else if (response.status === 409) {
        button.nextElementSibling.remove();
        button.replaceWith(inFridge(body.id));
      } else if (body.form_url) {
        location.href = body.form_url; // a detail is missing: finish it in the form, filled in
      } else {
        throw new Error(body.error || "Something went wrong.");
      }
    } catch (error) {
      button.disabled = false;
      button.textContent = `+ ${sources[kind].planned}`;
      say(error.message);
    }
  }

  // --- Events ------------------------------------------------------------------------

  opener.addEventListener("click", (event) => {
    event.preventDefault();
    if (panel.hidden) open();
    else close();
  });

  panel.querySelector(".quick-add-close").addEventListener("click", close);
  backdrop.addEventListener("click", close);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) close();
  });

  kindButtons.forEach((button) =>
    button.addEventListener("click", () => {
      setKind(button.dataset.kind);
      search();
      query.focus();
    }),
  );

  query.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(search, 300); // wait until the typing pauses
  });

  query.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      clearTimeout(timer);
      search();
    }
  });
})();
