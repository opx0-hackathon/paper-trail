import { StrictMode, lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

const SharedView = lazy(() => import("./SharedView"));

const root = document.getElementById("root");
if (!root) throw new Error("no root element");

const shared = window.location.pathname.match(/^\/s\/([\w-]+)$/);

createRoot(root).render(
  <StrictMode>
    {shared?.[1] ? (
      <Suspense fallback={null}>
        <SharedView token={shared[1]} />
      </Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
);
