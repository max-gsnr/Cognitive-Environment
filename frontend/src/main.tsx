import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { Shell } from "./Shell";
import "./styles.css";
import { AuditPage } from "./pages/AuditPage";
import { GeneratePage } from "./pages/GeneratePage";
import { IntakePage } from "./pages/IntakePage";
import { LandingPage } from "./pages/LandingPage";
import { PlayPage } from "./pages/PlayPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RosterPage } from "./pages/RosterPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "landing", element: <LandingPage /> },
      { path: "roster", element: <RosterPage /> },
      { path: "intake", element: <IntakePage /> },
      { path: "profiles/:profileId", element: <ProfilePage /> },
      { path: "profiles/:profileId/generate/:skillId", element: <GeneratePage /> },
      { path: "play/:profileId/:skillId", element: <PlayPage /> },
      { path: "audit", element: <AuditPage /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
