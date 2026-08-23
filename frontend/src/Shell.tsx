import { NavLink, Outlet } from "react-router-dom";

export function Shell() {
  return (
    <div className="shell">
      <header>
        <NavLink to="/" className="brand">
          Orbit
        </NavLink>
        <nav>
          <NavLink to="/">Roster</NavLink>
          <NavLink to="/intake">New child</NavLink>
          <NavLink to="/audit">Audit log</NavLink>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
