// A message like "Changes saved." pops up at the bottom of the page and fades away by itself.
// The ?msg= that brought it is removed from the address, so reloading doesn't show it again.
(() => {
  const toast = document.querySelector(".toast");
  if (!toast) return;

  const url = new URL(location.href);
  if (url.searchParams.has("msg")) {
    url.searchParams.delete("msg");
    history.replaceState(null, "", url);
  }

  // Errors stay a little longer, since they ask you to do something.
  const delay = toast.classList.contains("toast-error") ? 9000 : 4000;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches; // no fade, so no animationend
  setTimeout(() => {
    if (still) return toast.remove();
    toast.classList.add("is-leaving");
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
  }, delay);
  toast.addEventListener("click", () => toast.remove());
})();
