const search = document.getElementById("search");
const searchResults = document.getElementById("search-results");
const themePicker = document.getElementById("theme-picker");

const showResults = () => searchResults.classList.remove("hidden");
const hideResults = () => searchResults.classList.add("hidden");

// Keep the browser/PWA chrome color in sync with the active theme
const themeColor = document.querySelector('meta[name="theme-color"]');
const applyThemeColor = () => {
  const style = getComputedStyle(document.documentElement);
  const triplet = style.getPropertyValue("--surface-deep").trim();
  if (triplet) {
    themeColor.content = `rgb(${triplet.split(/\s+/).join(",")})`;
  }
};

// The theme itself is applied before first paint in base.html;
// here the picker is kept in sync and persists the choice
themePicker.value = document.documentElement.dataset.theme || "marquee";
applyThemeColor();
themePicker.addEventListener("change", () => {
  document.documentElement.dataset.theme = themePicker.value;
  localStorage.setItem("theme", themePicker.value);
  applyThemeColor();
});

// Show short feedback toasts, sent by the server in HX-Trigger headers
const toasts = document.getElementById("toasts");

const showToast = (message) => {
  const toast = document.createElement("div");
  toast.textContent = message;
  toast.className =
    "rounded-full bg-surface border border-accent/40 text-ink text-sm px-4 py-2 " +
    "shadow-lg shadow-black/40 transition duration-300 opacity-0 translate-y-2";
  toasts.append(toast);

  requestAnimationFrame(() => toast.classList.remove("opacity-0", "translate-y-2"));
  setTimeout(() => {
    toast.classList.add("opacity-0", "translate-y-2");
    setTimeout(() => toast.remove(), 300);
  }, 2500);
};

document.body.addEventListener("ramsey:toast", (event) => {
  showToast(event.detail.value);
});

// Open a random pick right away when launched from the PWA shortcut
if (new URLSearchParams(location.search).has("pick")) {
  history.replaceState(null, "", location.pathname);
  htmx.ajax("GET", "/watchlist/pick", "#modal");
}

// Lock page scrolling and trap focus while the detail view is open
const modal = document.getElementById("modal");
let modalOpen = false;

const modalFocusables = () =>
  [...modal.querySelectorAll("a[href], button, input, textarea, select")];

const syncModal = () => {
  const open = modal.childElementCount > 0;
  document.body.classList.toggle("overflow-hidden", open);
  if (open && !modalOpen) {
    (modal.querySelector('[title="Close"]') || modalFocusables()[0])?.focus();
  }
  modalOpen = open;
};

new MutationObserver(syncModal).observe(modal, { childList: true });

document.addEventListener("keydown", (event) => {
  if (!modalOpen || event.key !== "Tab") return;

  const items = modalFocusables();
  if (!items.length) return;

  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  } else if (!modal.contains(document.activeElement)) {
    event.preventDefault();
    first.focus();
  }
});

// Replace the native hx-confirm dialog with a themed one
const confirmBox = document.getElementById("confirm");
const confirmQuestion = document.getElementById("confirm-question");
let confirmAction = null;

const closeConfirm = () => {
  confirmBox.classList.add("hidden");
  confirmAction = null;
};

document.body.addEventListener("htmx:confirm", (event) => {
  if (!event.detail.question) return;

  event.preventDefault();
  confirmQuestion.textContent = event.detail.question;
  confirmAction = () => event.detail.issueRequest(true);
  confirmBox.classList.remove("hidden");
  document.getElementById("confirm-ok").focus();
});

document.getElementById("confirm-ok").addEventListener("click", () => {
  const action = confirmAction;
  closeConfirm();
  action?.();
});
document.getElementById("confirm-cancel").addEventListener("click", closeConfirm);
document.getElementById("confirm-backdrop").addEventListener("click", closeConfirm);

// Keyboard navigation for the search results
let activeRow = -1;

const searchRows = () => [...searchResults.querySelectorAll(".search-row")];

const highlightRow = () => {
  searchRows().forEach((row, index) => {
    row.classList.toggle("bg-accent/10", index === activeRow);
  });

  const row = searchRows()[activeRow];
  if (row) row.scrollIntoView({ block: "nearest" });
};

search.addEventListener("keydown", (event) => {
  const rows = searchRows();
  if (!rows.length) return;

  if (event.key === "ArrowDown") {
    event.preventDefault();
    activeRow = Math.min(activeRow + 1, rows.length - 1);
    highlightRow();
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    activeRow = Math.max(activeRow - 1, 0);
    highlightRow();
  } else if (event.key === "Enter" && activeRow >= 0) {
    event.preventDefault();
    rows[activeRow].querySelector("button").click();
  }
});

// Show the dropdown when a search returns results, hide it after a
// movie is saved from the results, and re-apply the library filter
// whenever the library re-renders
document.body.addEventListener("htmx:afterSwap", (event) => {
  if (event.detail.target === searchResults) {
    activeRow = -1;
    if (searchResults.textContent.trim() !== "") {
      showResults();
    } else {
      hideResults();
    }
  } else if (event.detail.target.id === "library") {
    hideResults();
  }
});

search.addEventListener("focus", () => {
  if (searchResults.textContent.trim() !== "") {
    showResults();
  }
});

// Hide the dropdown when clicking outside the search bar and results
document.addEventListener("mousedown", (event) => {
  if (event.target !== search && !searchResults.contains(event.target)) {
    hideResults();
  }
});

// Add '/' as a shortcut for the search bar, and Escape to close
// the results and the detail view
document.addEventListener("keyup", (event) => {
  if (event.code === "Slash") {
    search.focus();
    return;
  }

  if (event.code === "Escape") {
    search.blur();
    hideResults();
    closeConfirm();
    document.getElementById("modal").replaceChildren();
  }
});
