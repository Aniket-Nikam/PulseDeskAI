import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Dismiss the loading screen after React has mounted
requestAnimationFrame(() => {
  setTimeout(() => {
    const loader = document.getElementById("pd-loader");
    if (loader) {
      loader.classList.add("pd-loader-hide");
      loader.addEventListener("transitionend", () => loader.remove(), { once: true });
    }
  }, 300);
});
