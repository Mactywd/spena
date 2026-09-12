import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

// Le icone stanno qui, disegnate a mano e non prese da una libreria: sono tre, e una
// dipendenza di icone peserebbe sul primo avvio di una PWA più di quanto valga.
// `aria-hidden` non è opzionale — il nome accessibile del link deve restare la
// parola, altrimenti chi usa uno screen reader sente due volte la stessa scheda.
const ICONS: Record<string, ReactNode> = {
  lista: (
    <>
      <path d="M4 6.5h10M4 12h10M4 17.5h6" />
      <path d="M17 15.5l2 2 3.5-4" />
    </>
  ),
  dispensa: (
    <>
      <path d="M4 8.5h16v11.5H4z" />
      <path d="M3 4.5h18v4H3z" />
      <path d="M10.5 13h3" />
    </>
  ),
  ricette: (
    <>
      <path d="M12 7.5v12" />
      <path d="M12 7.5C12 6 10 4.5 6.5 4.5H3.5v13h3C9.5 17.5 12 19 12 19" />
      <path d="M12 7.5C12 6 14 4.5 17.5 4.5h3v13h-3C14.5 17.5 12 19 12 19" />
    </>
  ),
};

const TABS = [
  { to: "/lista", label: "Lista", icon: "lista" },
  { to: "/dispensa", label: "Dispensa", icon: "dispensa" },
  { to: "/ricette", label: "Ricette", icon: "ricette" },
];

export function TabBar() {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 border-t border-line bg-card"
      style={{ paddingBottom: "var(--safe-bottom)" }}
    >
      {/* la stessa larghezza massima del contenuto: su uno schermo largo una barra
          che attraversa tutto mentre l'app sta in mezzo sembra di un'altra pagina */}
      <div className="mx-auto grid max-w-md grid-cols-3">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `flex min-h-14 flex-col items-center justify-center gap-1 text-xs ${
                isActive ? "font-semibold text-brand" : "text-ink-faint"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={`rounded-full px-3 py-0.5 transition-colors ${
                    isActive ? "bg-brand-tint" : ""
                  }`}
                >
                  <svg
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                    className="size-6"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    {ICONS[tab.icon]}
                  </svg>
                </span>
                {tab.label}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
