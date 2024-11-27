const updateWatched = async (movie, direction) => {
  // Update the amount of times a movie was watched
  const response = await fetch("/api/update-movie", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier: movie, action: direction }),
  });

  const json = await response.json();
  if (json.status === 200) {
    console.log("Updated amount");

    if (json.data.new_amount <= 0) {
      window.location.reload();
    }
  }
};
