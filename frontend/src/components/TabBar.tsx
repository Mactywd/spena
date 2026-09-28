import { Link, useLocation } from "react-router-dom";
import { IconBox, IconListCheck, IconToolsKitchen2, type IconComponent } from "./ui/icons";

// `also`: i percorsi che stanno dentro una scheda senza cominciare col suo indirizzo.
// «Sistema la spesa» è una parte della lista (dal giro di T3: su /sistema la barra
// non segnava niente, e non si capiva dove si era).
const TABS: { to: string; label: string; icon: IconComponent; also?: string[] }[] = [
  { to: "/lista", label: "Lista", icon: IconListCheck, also: ["/sistema"] },
  { to: "/dispensa", label: "Dispensa", icon: IconBox },
  { to: "/ricette", label: "Ricette", icon: IconToolsKitchen2 },
];

export function TabBar() {
  const { pathname } = useLocation();
  return (
    <nav
      className="fixed inset-x-0 bottom-0 border-t border-line bg-card"
      style={{ paddingBottom: "var(--safe-bottom)" }}
    >
      {/* la stessa larghezza massima del contenuto: su uno schermo largo una barra
          che attraversa tutto mentre l'app sta in mezzo sembra di un'altra pagina */}
      <div className="mx-auto grid max-w-md grid-cols-3">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          // `NavLink` (react-router 7) rifiuta un `aria-current` passato a mano: quando il
          // suo stesso confronto con `to` non combacia, lo sovrascrive sempre a `undefined`
          // (chunk-BV7QT456.mjs:10714), scartando quanto passato per i percorsi di `also` —
          // misurato con il test sotto. Per questo il confronto è qui, uguale a quello che
          // `NavLink` farebbe da sé (`end` non passato, quindi combacia anche sui percorsi
          // annidati), e il link è un `Link` semplice.
          const pathActive = pathname === tab.to || pathname.startsWith(`${tab.to}/`);
          const alsoActive = tab.also?.some((p) => pathname === p || pathname.startsWith(`${p}/`)) ?? false;
          const active = pathActive || alsoActive;
          return (
            <Link
              key={tab.to}
              to={tab.to}
              // per i percorsi di `also` va messo a mano, o lo screen reader non saprebbe
              // dove si è
              aria-current={active ? "page" : undefined}
              className={`flex min-h-14 flex-col items-center justify-center gap-1 text-xs ${
                active ? "font-semibold text-brand" : "text-ink-faint"
              }`}
            >
              <span
                className={`rounded-full px-3 py-0.5 transition-colors ${
                  active ? "bg-brand-tint" : ""
                }`}
              >
                {/* `aria-hidden`: il nome del link resta la parola, o chi usa uno
                    screen reader sentirebbe due volte la stessa scheda */}
                <Icon aria-hidden="true" className="size-6" stroke={1.6} />
              </span>
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
