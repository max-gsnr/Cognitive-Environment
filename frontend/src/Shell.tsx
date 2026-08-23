import { NavLink, Outlet, useLocation } from "react-router-dom";

export function Shell() {
  const location = useLocation();
  const isLanding = location.pathname === "/" || location.pathname === "/landing";

  return (
    <div className="shell" style={isLanding ? { margin: 0, padding: 0, overflowX: "hidden" } : undefined}>
      {!isLanding && (
        <header>
          <NavLink to="/" className="brand">
            NEURO
          </NavLink>
          <nav>
            <NavLink to="/">Home</NavLink>
            <NavLink to="/roster">Roster</NavLink>
            <NavLink to="/intake">New child</NavLink>
            <NavLink to="/audit">Audit log</NavLink>
          </nav>
        </header>
      )}
      <main style={isLanding ? { maxWidth: "100%", margin: 0, padding: 0, width: "100%" } : undefined}>
        <Outlet />
      </main>
    </div>
  );
}
