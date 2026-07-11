const updateWatched = async (movie, direction) => {
  // Update the amount of times a movie was watched
  const response = await fetch("/api/update-movie", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier: movie, action: direction }),
  });

  const json = await response.json();
  if (json.status === 200) {
    window.location.reload();
  }
};

const deleteMovie = async (movie) => {
  // Delete a movie and its watch history
  if (!confirm("Remove this movie and its watch history?")) return;

  const response = await fetch("/api/delete-movie", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier: movie }),
  });

  const json = await response.json();
  if (json.status === 200) {
    window.location.reload();
  }
};
