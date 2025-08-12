function controlDrawer(drawer, action) {
  fetch("/control", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ drawer, action }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.status) {
        document.getElementById(
          `drawer${String.fromCharCode(64 + drawer)}-status`
        ).innerText = data.status;
      }
    });
}

function refreshStatus() {
  fetch("/get_status")
    .then((res) => res.json())
    .then((data) => {
      for (let i = 1; i <= 3; i++) {
        const letter = String.fromCharCode(64 + i);
        document.getElementById(`drawer${letter}-status`).innerText = data[i];
      }
    });
}
