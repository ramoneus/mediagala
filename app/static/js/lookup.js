// "Find it online": search a free online database for the chosen kind and fill in the
// form from the picked result. Everything stays editable, and the form works without it.
(() => {
  const box = document.querySelector("[data-lookup]");
  if (!box) return;

  const form = box.closest("form");
  const sources = JSON.parse(box.dataset.sources); // {kind: {name, notice}}
  const query = box.querySelector("#lookup-query");
  const list = box.querySelector("#lookup-results");
  const status = box.querySelector("#lookup-status");
  const notice = box.querySelector("[data-lookup-notice]");
  const posterUrl = form.querySelector('input[name="poster_url"]');
  const posterPreview = form.querySelector(".online-poster");

  let timer = null;
  let pending = null; // AbortController of the request in flight, so stale answers are dropped

  const currentKind = () => form.querySelector('input[name="kind"]:checked').value;

  function say(message) {
    status.textContent = message;
  }

  async function getJson(url) {
    if (pending) pending.abort();
    pending = new AbortController();
    const response = await fetch(url, { signal: pending.signal });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Something went wrong.");
    return body;
  }

  function showResults(results) {
    list.replaceChildren(
      ...results.map((match) => {
        const item = document.createElement("li");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "lookup-result";
        if (match.thumb_url) {
          const img = document.createElement("img");
          img.src = match.thumb_url;
          img.alt = "";
          img.loading = "lazy";
          button.append(img);
        }
        const text = document.createElement("span");
        const name = document.createElement("strong");
        name.textContent = match.title;
        const meta = document.createElement("small");
        meta.textContent = [match.year, match.author, match.genre].filter(Boolean).join(" · ");
        text.append(name, meta);
        button.append(text);
        button.addEventListener("click", () => pick(match));
        item.append(button);
        return item;
      }),
    );
    list.hidden = results.length === 0;
  }

  async function search() {
    const kind = currentKind();
    const text = query.value.trim();
    if (!(kind in sources) || text.length < 2) {
      showResults([]);
      say("");
      return;
    }
    say(`Searching ${sources[kind].name}…`);
    try {
      const body = await getJson(`/lookup/${kind}?q=${encodeURIComponent(text)}`);
      showResults(body.results);
      say(body.results.length ? `Results from ${body.source}. Pick one to fill in the form.` : "Nothing found. Try another spelling.");
    } catch (error) {
      if (error.name !== "AbortError") say(error.message);
    }
  }

  function setField(selector, value) {
    const field = form.querySelector(selector);
    if (field && value !== null && value !== undefined && value !== "") field.value = value;
  }

  function setPoster(url) {
    posterUrl.value = url;
    posterPreview.querySelector("img").src = url;
    posterPreview.hidden = !url;
  }

  async function pick(match) {
    say(match.title ? `Getting the details of ${match.title}…` : "Getting the details…");
    try {
      const { result, source } = await getJson(`/lookup/${currentKind()}/${match.source_id}`);
      setField("#title", result.title);
      setField("#year", result.year);
      setField("#author", result.author);
      setField("#pages", result.pages);
      setField("#description", result.description);
      const genre = form.querySelector("#genre");
      if ([...genre.options].some((option) => option.value === result.genre)) genre.value = result.genre;

      if (result.seasons.length) {
        const count = form.querySelector("#season_count");
        count.value = result.seasons.length;
        count.dispatchEvent(new Event("input")); // title-form.js adds or removes the season rows
        form.querySelectorAll('input[name="season_episodes"]').forEach((input, i) => {
          input.value = result.seasons[i];
        });
      }
      if (result.image_url) setPoster(result.image_url);

      showResults([]);
      query.value = "";
      say(`Filled in from ${source}. Check the details, then choose your status.`);
    } catch (error) {
      if (error.name !== "AbortError") say(error.message);
    }
  }

  query.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(search, 350); // wait until the user pauses typing
  });

  // Enter searches right away instead of submitting the whole form.
  query.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      clearTimeout(timer);
      search();
    }
  });

  // Each kind has its own database: name it in the box (with any credit it asks for),
  // and start the search over on a switch.
  function showSource() {
    const source = sources[currentKind()];
    if (source) query.placeholder = `Search ${source.name}…`;
    notice.textContent = source ? source.notice : "";
  }

  form.addEventListener("change", (event) => {
    if (event.target.name === "kind") {
      showResults([]);
      say("");
      showSource();
    }
  });
  showSource();

  form.querySelector("[data-drop-online-poster]").addEventListener("click", () => setPoster(""));

  // "⋯" in the quick add opens this form as /titles/new?kind=…&pick=<result>: fill it in from that result.
  const picked = new URLSearchParams(location.search).get("pick");
  if (picked && currentKind() in sources) pick({ source_id: picked, title: "" });
})();
