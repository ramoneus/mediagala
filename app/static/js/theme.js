// Light/dark theme switch. base.html already applied the saved (or system) theme
// before the page painted; this wires up the header button and remembers the choice.
(() => {
  const button = document.querySelector(".theme-toggle");
  if (!button) return;

  const root = document.documentElement;
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

  function savedTheme() {
    try {
      return localStorage.getItem("theme");
    } catch (e) {
      return null;
    }
  }

  function apply(theme) {
    root.dataset.theme = theme;
    const dark = theme === "dark";
    button.setAttribute("aria-pressed", String(dark));
    button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  }

  button.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    apply(next);
    try {
      localStorage.setItem("theme", next);
    } catch (e) {
      // Storage can be blocked (private mode); the switch still works for this page.
    }
  });

  // Follow system changes until the user picks a theme themselves.
  systemDark.addEventListener("change", (event) => {
    if (!savedTheme()) apply(event.matches ? "dark" : "light");
  });

  apply(root.dataset.theme === "dark" ? "dark" : "light");
})();
