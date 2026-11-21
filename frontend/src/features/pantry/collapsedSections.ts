import { useEffect, useState } from "react";
import { sectionOpen } from "./pantryView";

/** Dove si ricordano i reparti chiusi della dispensa (spec S15 §4, deciso da Mattia il
 * 2026-10-07). `localStorage` e non `sessionStorage`, a differenza dei filtri del
 * ricettario e del mondo di S14: chiudere «Spezie» perché non si guardano mai è una
 * disposizione della propria dispensa, come l'ordine delle cartelle, e ritrovarla domani
 * è il punto. Si salvano i **chiusi** e non gli aperti: un reparto nuovo nasce aperto, e
 * chi non ha mai chiuso niente vede la dispensa di sempre. */
export const COLLAPSED_KEY = "spena.dispensa.reparti-chiusi";

const NONE: ReadonlySet<string> = new Set();

/** Il `localStorage`, se si riesce ad aprirlo: già leggerlo può lanciare (dati del sito
 * bloccati), quindi anche l'accesso sta nel try. */
function localStore(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

/** I reparti chiusi ricordati, o nessuno. Un valore illeggibile vale «tutto aperto»; un
 * elemento che non è un nome si scarta. Un nome che non è un reparto della dispensa di
 * oggi resta e non fa niente: nessun gruppo si chiama così. */
export function loadCollapsed(store: Storage | null = localStore()): ReadonlySet<string> {
  if (store === null) return NONE;
  let saved: unknown;
  try {
    saved = JSON.parse(store.getItem(COLLAPSED_KEY) ?? "[]");
  } catch {
    return NONE;
  }
  if (!Array.isArray(saved)) return NONE;
  return new Set(saved.filter((name): name is string => typeof name === "string" && name !== ""));
}

/** Scrive i reparti chiusi, in ordine. Se non si può (memoria piena o bloccata), lo stato
 * vale lo stesso finché lo schermo è aperto: il ricordo è una comodità, non una
 * condizione. */
export function saveCollapsed(
  collapsed: ReadonlySet<string>,
  store: Storage | null = localStore()
): void {
  if (store === null) return;
  try {
    store.setItem(COLLAPSED_KEY, JSON.stringify([...collapsed].sort()));
  } catch {
    // vedi sopra: niente da fare, e niente da dire
  }
}

/** Lo stesso insieme se `category` ci sta già come si chiede, uno nuovo altrimenti: così
 * React non ridisegna per un tocco che non cambia niente. */
function withMember(set: ReadonlySet<string>, category: string, member: boolean): ReadonlySet<string> {
  if (set.has(category) === member) return set;
  const next = new Set(set);
  if (member) next.add(category);
  else next.delete(category);
  return next;
}

/** Due insiemi con gli stessi elementi. */
function sameMembers(a: ReadonlySet<string>, b: ReadonlySet<string>): boolean {
  if (a.size !== b.size) return false;
  for (const member of a) if (!b.has(member)) return false;
  return true;
}

/** Lo stato dei reparti della Dispensa. `filtering` è una ricerca scritta o il riepilogo
 * delle scadenze premuto: aprono i reparti senza salvare (`sectionOpen`). `setOpen` è un
 * gesto dell'utente — il tocco sul titolo, o la voce appena aggiunta (spec S15 §3) — e
 * si salva sempre, anche durante un filtro; chiudere durante un filtro si ricorda anche
 * in `closedWhileFiltering`, finché il filtro resta acceso, o il reparto resterebbe
 * aperto sotto il dito.
 *
 * Il riepilogo che lo schermo spegne da solo (l'ultima voce in scadenza tolta o finita)
 * lascia aperto a video quel che mostrava, senza salvarlo (decisione 3): `held`, che non
 * va mai in `saveCollapsed` e si lascia andare al primo gesto di chi guarda. Si ricorda
 * a ogni disegno col filtro (`noteFiltered`) e non al momento in cui si spegne, perché
 * quando si spegne le righe in scadenza non ci sono più (decisione 12). `noteFiltered`
 * cambia stato nel disegno, come le altre due righe di questo file, e per questo
 * confronta prima di scrivere: lo stesso insieme non ridisegna. */
export function useCollapsedSections(filtering: boolean) {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => loadCollapsed());
  const [closedWhileFiltering, setClosedWhileFiltering] = useState<ReadonlySet<string>>(NONE);
  const [held, setHeld] = useState<ReadonlySet<string>>(NONE);
  const [shownByFilter, setShownByFilter] = useState<ReadonlySet<string>>(NONE);
  // spento il filtro, quel che si era chiuso durante non conta più: la prossima ricerca
  // riapre ogni reparto che ha un risultato. Si azzera qui, durante il disegno, come fa la
  // Dispensa col riepilogo che sparisce: niente giro con uno stato vecchio
  if (!filtering && closedWhileFiltering.size > 0) setClosedWhileFiltering(NONE);

  useEffect(() => {
    saveCollapsed(collapsed);
  }, [collapsed]);

  const release = () => setHeld((prev) => (prev.size === 0 ? prev : NONE));

  return {
    isOpen: (category: string) =>
      sectionOpen(category, { collapsed, filtering, closedWhileFiltering, held }),
    setOpen: (category: string, open: boolean) => {
      setCollapsed((prev) => withMember(prev, category, !open));
      setClosedWhileFiltering((prev) => withMember(prev, category, !open && filtering));
      release();
    },
    noteFiltered: (categories: readonly string[]) => {
      const shown = new Set(categories.filter((category) => !closedWhileFiltering.has(category)));
      if (!sameMembers(shown, shownByFilter)) setShownByFilter(shown);
    },
    holdFiltered: () => setHeld(shownByFilter),
    releaseHold: release,
  };
}
