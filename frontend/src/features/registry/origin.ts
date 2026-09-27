/** Da dove si è aperta una scheda dell'anagrafica, e quindi dove porta il tasto
 * indietro.
 *
 * Le schede si raggiungono da due posti — la dispensa e la pagina «Anagrafica» — e
 * `Screen` vuole una destinazione dichiarata, non `navigate(-1)` (T1). Chi apre la
 * scheda lo scrive nell'indirizzo: `?da=dispensa` torna alla dispensa, senza si torna
 * all'anagrafica. Il parametro segue la navigazione fra le schede, così dal prodotto
 * all'ingrediente e ritorno il tasto indietro porta ancora dove si era partiti. */
export type Origin = "dispensa" | null;

export function originFrom(da: string | null): Origin {
  return da === "dispensa" ? "dispensa" : null;
}

export function backFrom(origin: Origin): { to: string; label: string } {
  return origin === "dispensa"
    ? { to: "/dispensa", label: "Dispensa" }
    : { to: "/anagrafica", label: "Anagrafica" };
}

function withOrigin(path: string, origin: Origin): string {
  return origin === "dispensa" ? `${path}?da=dispensa` : path;
}

export function ingredientPath(id: string, origin: Origin): string {
  return withOrigin(`/anagrafica/ingrediente/${id}`, origin);
}

export function productPath(id: string, origin: Origin): string {
  return withOrigin(`/anagrafica/prodotto/${id}`, origin);
}
