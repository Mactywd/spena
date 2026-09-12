import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/lista", label: "Lista" },
  { to: "/dispensa", label: "Dispensa" },
  { to: "/ricette", label: "Ricette" },
];

export function TabBar() {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 grid grid-cols-3 border-t border-neutral-200 bg-white"
      style={{ paddingBottom: "var(--safe-bottom)" }}
    >
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) =>
            `py-3 text-center text-sm ${isActive ? "font-semibold text-emerald-700" : "text-neutral-500"}`
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
