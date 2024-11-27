const search = document.getElementById("search");
const searchResults = document.getElementById("search-results");

// Check periodically if the results should be hidden
setInterval(() => {
  if (searchResults.textContent.trim() !== "") {
    searchResults.classList.add("show-results");
    searchResults.classList.remove("hidden");
    return;
  }
}, 20);

search.addEventListener("focus", () => {
  if (searchResults.textContent.trim() !== "") {
    searchResults.classList.add("show-results");
    searchResults.classList.remove("hidden");
  }
});

search.addEventListener("focusout", () => {
  searchResults.classList.remove("show-results");
  searchResults.classList.add("hidden");
});

search.addEventListener("input", () => {
  if (search.value.trim() !== "") {
    searchResults.classList.add("show-results");
    searchResults.classList.remove("hidden");
  } else {
    searchResults.classList.remove("show-results");
    searchResults.classList.add("hidden");
  }
});

// Add '/' as a shortcut for the search bar
document.addEventListener(
  "keyup",
  (event) => {
    if (event.code === "Slash") {
      event.preventDefault();
      search.focus();
      return;
    }

    if (event.code === "Escape") {
      console.log("escape pressed");
      event.preventDefault();
      search.parentElement.focus();
      return;
    }
  },
  false,
);

const storeMovieResult = async (movie) => {
  response = await fetch("/api/save-movie", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ identifier: movie }),
  });
  json = await response.json();

  if (json.status === 200) {
    console.log("Movie saved!");
    window.location.reload();
  }
};
