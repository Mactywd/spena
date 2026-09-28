import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation } from "react-router-dom";
import { BrandMark } from "./ui/BrandMark";
import { IconMenu2, IconX } from "./ui/icons";

// L'indice completo (D3, T1): le sezioni che la barra in basso non porta. Pasti,
// Spese, Profilo e Connettori si aggiungeranno qui quando esisteranno.
const INDEX = [
  { to: "/sistema", label: "Sistema la spesa" },
  { to: "/ricette/importa", label: "Ingredienti da abbinare" },
  { to: "/anagrafica", label: "Anagrafica" },
];

const FOCUSABLE = "a[href], button:not([disabled])";

/** L'intestazione che sta sopra ogni schermata.
 *
 * `sticky` e non `fixed`: fissa, dovrebbe riservarsi lo spazio con un margine sul
 * contenuto, e quel margine si dimentica il giorno in cui l'altezza cambia.
 *
 * A destra il ☰ dell'indice completo (T1): apre un pannello con le sezioni che la
 * barra in basso non porta. È arrivato con la prima sezione secondaria vera,
 * l'anagrafica (S9), come D3 aveva deciso. Il pannello è un dialogo: il fuoco ci entra
 * e non ne esce col tabulatore, Esc e il tocco sul velo lo chiudono, e il fuoco torna
 * al ☰ — chi naviga da tastiera o con la voce resta dov'era.
 */
export function AppHeader() {
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    toggleRef.current?.focus();
  }, []);

  // avanti/indietro del browser cambia l'indirizzo senza passare da un `Link` di
  // qui dentro (quello chiude già da sé, scelto a mano sopra): senza questo il
  // pannello restava aperto sopra una pagina che non è più la sua. Durante il
  // disegno e non in un effetto, come `seen` in InlineField: un effetto chiuderebbe
  // un fotogramma dopo, con il pannello ancora a video sopra la pagina nuova; non
  // `close()`, niente fuoco da riportare al ☰, che la navigazione sta già spostando.
  const location = useLocation();
  const [lastPathname, setLastPathname] = useState(location.pathname);
  if (location.pathname !== lastPathname) {
    setLastPathname(location.pathname);
    setOpen(false);
  }

  // Col pannello aperto la pagina sotto non scorre: il dito che scorre sul velo o sul
  // pannello muoverebbe la lista dietro, e chiuso il menu non si sarebbe più dove si
  // era. Il valore di prima si rimette al ritorno dell'effetto, che corre a ogni
  // chiusura — dal ☰, da Esc, dal velo, da una voce, da un cambio di pagina che
  // chiude durante il disegno — e anche se l'intestazione sparisce a menu aperto.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      const panel = panelRef.current;
      if (event.key !== "Tab" || !panel) return;
      const targets = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (targets.length === 0) return;
      const first = targets[0];
      const last = targets[targets.length - 1];
      if (!panel.contains(document.activeElement)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, close]);

  return (
    <header role="banner" className="sticky top-0 z-10 h-12 border-b border-line bg-card">
      {/* l'altezza sta sull'header, non su questo div: il bordo dell'header è nella
          sua stessa scatola (box-sizing: border-box, dal preflight di Tailwind), e
          49px (48 + 1 di bordo) contro i 48 che `main` riserva con
          `calc(100dvh-3rem)` sono la differenza verticale che frontend/e2e/style.spec.ts
          ora controlla e che qui misurava un pixel di scorrimento in più */}
      <div className="mx-auto flex h-full max-w-md items-center justify-between px-4">
        <Link
          to="/"
          className="flex min-h-11 items-center gap-2 font-semibold tracking-tight text-brand"
        >
          <BrandMark className="size-7" />
          Spena
        </Link>
        <button
          ref={toggleRef}
          type="button"
          aria-label="Apri il menu"
          aria-haspopup="dialog"
          aria-expanded={open}
          onClick={() => setOpen(true)}
          className="-mr-2 flex size-11 items-center justify-center rounded-full text-ink-soft"
        >
          <IconMenu2 aria-hidden="true" className="size-6" stroke={1.8} />
        </button>
      </div>

      {open &&
        createPortal(
          // in un portale su document.body (ruling F4): l'header è `sticky z-10`, un
          // suo stacking context, e le barre sticky degli schermi (su /lista
          // `AddItemField` è `sticky top-12 z-5`) e l'avviso (`z-20`) vivono ciascuno
          // nel proprio. Il portale mette menu e velo sopra tutti loro con un solo
          // `z-30`, senza dover inseguire lo z-index di ognuno
          <div className="fixed inset-0 z-30">
            {/* il tocco fuori chiude: il velo è un bersaglio, non una decorazione. Fuori
                dall'albero accessibile, perché per chi non lo vede la chiusura è Esc o
                «Chiudi il menu». `scrim` e non `ink`: in scuro `ink` è chiaro, e il
                velo schiarirebbe la pagina invece di spegnerla */}
            <div
              data-menu-backdrop=""
              aria-hidden="true"
              onClick={close}
              className="absolute inset-0 bg-scrim/40"
            />
            <div
              ref={panelRef}
              role="dialog"
              aria-modal="true"
              aria-label="Menu"
              className="absolute inset-y-0 right-0 flex w-72 max-w-[85vw] flex-col bg-card px-4 pt-1 pb-[calc(1rem+var(--safe-bottom))]"
            >
              <div className="flex min-h-11 items-center justify-between">
                <span className="font-semibold tracking-tight">Menu</span>
                <button
                  type="button"
                  aria-label="Chiudi il menu"
                  onClick={close}
                  className="-mr-2 flex size-11 items-center justify-center rounded-full text-ink-soft"
                >
                  <IconX aria-hidden="true" className="size-5" stroke={2} />
                </button>
              </div>
              <nav aria-label="Indice">
                <ul className="divide-y divide-line">
                  {INDEX.map((entry) => (
                    <li key={entry.to}>
                      {/* scelta una voce si chiude e basta: la navigazione porta altrove,
                          e rendere il fuoco al ☰ lo toglierebbe alla pagina nuova */}
                      <Link
                        to={entry.to}
                        onClick={() => setOpen(false)}
                        className="flex min-h-12 items-center text-base font-medium text-ink"
                      >
                        {entry.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            </div>
          </div>,
          document.body
        )}
    </header>
  );
}
