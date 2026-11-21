import type { PantryItem } from "../../domain/types";

/** Il nome con cui l'utente chiama questa voce: il prodotto se c'è, l'ingrediente
 * altrimenti. Entra nei nomi accessibili dei controlli della riga («Togli Total 0%
 * dalla dispensa»), perché due barattoli dello stesso ingrediente vanno distinti. */
export function itemLabel(item: PantryItem): string {
  return item.product_name ?? item.ingredient_name;
}

// minuscole e senza accenti: chi cerca «caffe» vuole il caffè
function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

/** Se la voce risponde a quel che è scritto nella barra (S11). Guarda ingrediente,
 * prodotto e marca: si cerca «fage» come si cerca «yogurt». */
export function matchesQuery(item: PantryItem, query: string): boolean {
  const wanted = fold(query);
  if (!wanted) return true;
  return [item.ingredient_name, item.product_name, item.product_brand].some(
    (field) => field !== null && fold(field).includes(wanted)
  );
}

/** Se la voce entra nel riepilogo delle scadenze. Il verdetto è del backend
 * (`expiry`); qui si toglie solo ciò che è finito, perché un barattolo vuoto non ha
 * più niente da consumare in tempo. */
export function isExpiring(item: PantryItem): boolean {
  return item.expiry !== null && item.status !== "finished";
}

/** Se la voce resta in vista col riepilogo premuto. Non è `isExpiring`: il conteggio
 * lascia fuori le finite, la vista no. Una voce segnata «Finito» dal filtro deve
 * restare lì, in fondo alla sua sezione, con il suo «In lista»: sparire sotto le dita
 * si porterebbe via proprio la strada che rimette in lista quel che è finito. */
export function hasExpiry(item: PantryItem): boolean {
  return item.expiry !== null;
}

/** Il mondo che la Dispensa mostra (S14): tutto, solo il cibo, solo le cose di casa.
 * «Casa» è `non_food`, cioè i reparti `casa` e `igiene`; quale voce stia dove lo dice il
 * server (`ingredient_kind`), non questo file. */
export type PantryWorld = "all" | "food" | "non_food";

/** L'ordine dei pulsanti del selettore. */
export const WORLDS: readonly PantryWorld[] = ["all", "food", "non_food"];

/** I nomi a video, decisi da Mattia il 2026-10-07: «Casa» e non «Non alimentari», che a
 * 375 px non ci sta. Servono anche al vuoto del mondo («Niente in Casa per «…»»). */
export const WORLD_LABELS: Record<PantryWorld, string> = {
  all: "Tutto",
  food: "Cibo",
  non_food: "Casa",
};

/** Se la voce sta nel mondo scelto. Un confronto su un verdetto del server e non un
 * calcolo: il mondo discende dal reparto in `kind_for_category`, nel backend, e una
 * seconda copia qui resterebbe indietro il giorno in cui un reparto cambia mondo. */
export function inWorld(item: PantryItem, world: PantryWorld): boolean {
  return world === "all" || item.ingredient_kind === world;
}

/** Se in dispensa ci sono voci dei due mondi: solo allora il selettore serve (bozza S14
 * §3). Con un mondo solo, ogni scelta diversa da «Tutto» potrebbe solo svuotare la
 * pagina. Contano tutte le voci che arrivano, finite comprese: sono a video. */
export function hasBothWorlds(items: PantryItem[]): boolean {
  return (
    items.some((item) => item.ingredient_kind === "food") &&
    items.some((item) => item.ingredient_kind === "non_food")
  );
}

/** Quel che chi guarda ha chiesto alla Dispensa: il mondo, il testo della barra, il
 * riepilogo delle scadenze premuto. */
export interface PantryView {
  world: PantryWorld;
  query: string;
  expiringOnly: boolean;
}

/** Le voci a video, coi filtri in un ordine solo (bozza S14 §4): mondo, ricerca (S11),
 * in scadenza. Il raggruppamento per reparto viene dopo (`groupForDisplay`), e un reparto
 * senza voci del mondo scelto sparisce intero: non è chiuso, non c'è. */
export function visibleItems(items: PantryItem[], view: PantryView): PantryItem[] {
  return items
    .filter((item) => inWorld(item, view.world))
    .filter((item) => matchesQuery(item, view.query))
    .filter((item) => !view.expiringOnly || hasExpiry(item));
}

/** Il mondo da applicare davvero, dato quello scelto. Torna «Tutto» in due casi:
 * - il selettore non c'è più (un mondo solo): una dispensa vuota per un filtro che non si
 *   vede sarebbe una bugia, come per il riepilogo delle scadenze che sparisce;
 * - la voce appena aggiunta e in attesa di essere portata in vista (`revealId`; la serie
 *   della scansione non ne passa finché il pannello è aperto) è dell'altro mondo: deve
 *   potersi vedere, come dopo un'aggiunta la barra si svuota e il riepilogo si spegne.
 * Una voce appena aggiunta dello stesso mondo si vede già, e il mondo resta. Una che non
 * è ancora arrivata nell'elenco non cambia niente: se ne riparla quando arriva. */
export function settleWorld(
  world: PantryWorld,
  items: PantryItem[],
  revealId: string | null
): PantryWorld {
  if (world === "all") return world;
  if (!hasBothWorlds(items)) return "all";
  const revealed = revealId === null ? undefined : items.find((item) => item.id === revealId);
  if (revealed !== undefined && !inWorld(revealed, world)) return "all";
  return world;
}

/** L'avviso dopo un'aggiunta. In serie la voce può finire in un mondo che il selettore
 * nasconde: il seguito dice dove è andata, perché non resti un vicolo cieco. Solo in
 * serie: dal «+» il selettore va a «Tutto» e la voce si vede comunque (decisione 5). */
export function enteredNotice(
  label: string,
  kind: PantryItem["ingredient_kind"],
  world: PantryWorld,
  series: boolean
): string {
  const base = `In dispensa: ${label}`;
  return series && world !== "all" && kind !== world
    ? `${base}, sotto «${WORLD_LABELS[kind]}»`
    : base;
}

export function expiryCounts(items: PantryItem[]): { soon: number; expired: number } {
  let soon = 0;
  let expired = 0;
  for (const item of items) {
    if (!isExpiring(item)) continue;
    if (item.expiry === "soon") soon += 1;
    else expired += 1;
  }
  return { soon, expired };
}

/** Il testo del riepilogo in cima alla dispensa, `null` se non c'è niente da dire:
 * il riepilogo compare solo quando serve (spec T3 §4.1). «Oltre la scadenza» e non
 * «scaduti»: il participio sbaglierebbe l'accordo su metà delle voci. */
export function expirySummary(counts: { soon: number; expired: number }): string | null {
  const parts: string[] = [];
  if (counts.soon > 0) parts.push(`${counts.soon} in scadenza questa settimana`);
  if (counts.expired > 0) parts.push(`${counts.expired} oltre la scadenza`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

/** Il riepilogo delle scadenze di un solo mondo: quel che la dispensa dice in cima è
 * quel che si vede con il selettore dov'è, non il totale di tutto. */
export function worldSummary(items: PantryItem[], world: PantryWorld): string | null {
  return expirySummary(expiryCounts(items.filter((item) => inWorld(item, world))));
}

/** Le sezioni a video: reparti in ordine alfabetico; dentro, l'ordine del server
 * (stabile da S21) con le voci finite in fondo (spec T3 §4.1). Il filtro è stabile:
 * le finite restano fra loro nell'ordine in cui arrivano. */
export function groupForDisplay(items: PantryItem[]): [string, PantryItem[]][] {
  const groups = new Map<string, PantryItem[]>();
  for (const item of items) {
    groups.set(item.ingredient_category, [...(groups.get(item.ingredient_category) ?? []), item]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([category, rows]) => [
      category,
      [...rows.filter((r) => r.status !== "finished"), ...rows.filter((r) => r.status === "finished")],
    ]);
}

// --- S15: i reparti che si aprono e si chiudono ---

/** Come sta un reparto a video (spec S15 §3). `collapsed` è quel che l'utente ha chiuso
 * e che si ricorda; `filtering` è una ricerca scritta o il riepilogo delle scadenze
 * premuto; `closedWhileFiltering` sono i reparti chiusi a mano mentre quel filtro era
 * acceso, e si svuota quando il filtro si spegne. */
export interface SectionView {
  collapsed: ReadonlySet<string>;
  filtering: boolean;
  closedWhileFiltering: ReadonlySet<string>;
  /** I reparti che il riepilogo aveva aperti quando lo schermo l'ha spento: restano
   * aperti anche se salvati come chiusi, finché l'utente non li chiude lui (decisioni 3
   * e 12 del piano dispensa-serie-reparti). Facoltativo, così i casi di prima non
   * cambiano; con un filtro acceso non conta, vale il filtro. */
  held?: ReadonlySet<string>;
}

/** Se un reparto è aperto a video. Un filtro mostra quel che ha trovato e non cambia
 * quel che l'utente aveva deciso: con un filtro acceso a video restano solo i reparti
 * che hanno un risultato, e sono aperti — salvo quelli che si chiudono a mano proprio
 * adesso, perché toccare il titolo durante una ricerca chiude per davvero. Spento il
 * filtro, vale il salvato. Il mondo di S14 non passa da qui: decide quali reparti ci
 * sono, non come stanno. */
export function sectionOpen(category: string, view: SectionView): boolean {
  return view.filtering
    ? !view.closedWhileFiltering.has(category)
    : !view.collapsed.has(category) || (view.held?.has(category) ?? false);
}

/** Quel che un reparto chiuso non deve nascondere (spec S15 §2): le voci finite, che
 * hanno il loro «In lista» da toccare, e quelle in scadenza o oltre, che hanno un tempo
 * che corre. Una finita conta una volta, come finita: è la regola del riepilogo in cima
 * (`isExpiring` lascia fuori le finite). */
export function attentionCounts(rows: PantryItem[]): { finished: number; expiring: number } {
  let finished = 0;
  let expiring = 0;
  for (const row of rows) {
    if (row.status === "finished") finished += 1;
    else if (isExpiring(row)) expiring += 1;
  }
  return { finished, expiring };
}

export function finishedText(count: number): string {
  return count === 1 ? "1 finito" : `${count} finiti`;
}

export function expiringText(count: number): string {
  return `${count} in scadenza`;
}
