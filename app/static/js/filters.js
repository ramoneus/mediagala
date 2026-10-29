// The filters on the home page apply as soon as one changes, so the "Apply" button is only
// needed without JavaScript. The search still runs on Enter, not on every key.
(() => {
  const toolbar = document.querySelector(".toolbar");
  if (!toolbar) return;

  toolbar.classList.add("auto-apply");
  toolbar.addEventListener("change", (event) => {
    if (event.target.matches("select")) toolbar.requestSubmit();
  });
})();
