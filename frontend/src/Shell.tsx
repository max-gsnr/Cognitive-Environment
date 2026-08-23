import { NavLink, Outlet, useLocation } from "react-router-dom";

export function Shell() {
  const location = useLocation();
  const isLanding = location.pathname === "/" || location.pathname === "/landing";

  return (
    <div className={`shell-root ${isLanding ? "landing-mode" : "grassy-world-mode"}`}>
      {!isLanding && (
        <>
          {/* 16-Bit Animated Pixel Clouds */}
          <div className="pixel-cloud-sky" aria-hidden="true">
            <div className="pixel-cloud cloud-slow" />
            <div className="pixel-cloud cloud-med" />
            <div className="pixel-cloud cloud-fast" />
          </div>

          {/* 16-Bit Retro Arcade Top Header */}
          <header className="retro-arcade-header">
            <NavLink to="/" className="brand-logo-link" title="NEURO Home">
              <img src="/neuro-logo.png" alt="NEURO" className="brand-logo-img" />
            </NavLink>
            <nav className="retro-nav">
              <NavLink to="/roster" className={({ isActive }) => `nav-btn ${isActive ? "active" : ""}`}>
                🎒 Student Roster
              </NavLink>
              <NavLink to="/intake" className={({ isActive }) => `nav-btn ${isActive ? "active" : ""}`}>
                ✨ New Child
              </NavLink>
              <NavLink to="/audit" className={({ isActive }) => `nav-btn ${isActive ? "active" : ""}`}>
                📜 Audit Log
              </NavLink>
            </nav>
          </header>
        </>
      )}

      <main className={`main-viewport ${isLanding ? "main-landing" : "main-elevated-world"}`}>
        <Outlet />
      </main>

      {!isLanding && (
        <footer className="pixel-grass-footer" aria-hidden="true">
          <div className="pixel-grass-blade-layer" />
          <div className="pixel-dirt-layer" />
        </footer>
      )}
    </div>
  );
}

