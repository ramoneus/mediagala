// Opens and closes the fridge door. Inside are the titles you have "open" (in progress).
// The whole door is clickable (except the magnets, which are filters), and the choice is remembered.
(() => {
  const fridge = document.querySelector("[data-fridge]");
  if (!fridge) return;

  const door = fridge.querySelector(".fridge-door-panel");
  const handle = fridge.querySelector(".fridge-handle-button");
  const inside = fridge.querySelector(".fridge-inside");

  function setOpen(open, remember = true) {
    fridge.classList.remove("is-peek");
    fridge.classList.toggle("is-open", open);
    handle.setAttribute("aria-expanded", String(open));
    handle.setAttribute("aria-label", open ? "Close the fridge" : "Open the fridge");
    // While the door is shut, keep the shelves out of keyboard and screen-reader reach.
    inside.toggleAttribute("inert", !open);
    if (remember) {
      try {
        localStorage.setItem("fridge-open", open ? "1" : "0");
      } catch (e) {
        // Storage can be blocked; the door still works for this page.
      }
    }
  }

  door.addEventListener("click", (event) => {
    if (event.target.closest(".magnet")) return; // magnets filter the list instead
    setOpen(!fridge.classList.contains("is-open"));
  });

  // The handle is on the outside of the door, so the open fridge has its own "Close" button.
  fridge.querySelector(".fridge-close").addEventListener("click", () => {
    setOpen(false);
    handle.focus();
  });

  // Restore the last state without playing the swing animation on page load.
  let saved = null;
  try {
    saved = localStorage.getItem("fridge-open");
  } catch (e) {}
  const startOpen = fridge.classList.contains("is-open") || saved === "1";
  fridge.classList.add("no-motion");
  setOpen(startOpen, false);
  requestAnimationFrame(() => requestAnimationFrame(() => fridge.classList.remove("no-motion")));
})();
