// Canonical mount point shipped by the platform, like index.html and
// vite.config.ts. The generated PoC owns App.tsx; this only renders it, so
// the build works whether or not the model wrote an entry module.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";

const container = document.getElementById("root");
if (!container) throw new Error("index.html is missing #root");

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
