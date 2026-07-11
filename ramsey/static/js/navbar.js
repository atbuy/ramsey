const search = document.getElementById("search");
const searchResults = document.getElementById("search-results");
const themePicker = document.getElementById("theme-picker");

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

const showResults = () => searchResults.classList.remove("hidden");
const hideResults = () => searchResults.classList.add("hidden");

// Show the dropdown when a search returns results, and hide it
// after a movie is saved from the results
document.body.addEventListener("htmx:afterSwap", (event) => {
  if (event.detail.target === searchResults) {
    if (searchResults.textContent.trim() !== "") {
      showResults();
    } else {
      hideResults();
    }
  } else if (event.detail.target.id === "watched-list") {
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

// Add '/' as a shortcut for the search bar, and Escape to close the results
document.addEventListener("keyup", (event) => {
  if (event.code === "Slash") {
    search.focus();
    return;
  }

  if (event.code === "Escape") {
    search.blur();
    hideResults();
    document.getElementById("modal").replaceChildren();
  }
});
