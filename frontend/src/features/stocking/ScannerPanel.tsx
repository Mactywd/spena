import { useCallback, useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { BarcodeScanner } from "./BarcodeScanner";
import type { ProductSuggestion } from "./CustomProductForm";
import { lookupBarcode } from "./api";
import { otherIngredient } from "./wording";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconPencilPlus, IconSearch } from "../../components/ui/icons";
import type { Product, ShoppingItem } from "../../domain/types";

/** Il pannello del codice a barre di una voce (spec T3 §4.3, S10): la fotocamera, il
 * codice scritto a mano con «Cerca», e ciò che il lookup risponde.
 *
 * Qui vivono, e solo qui, le guardie del codice: il prodotto di un altro ingrediente
 * che non si aggancia (il 409 della sistemazione tutto-o-niente), la cifra di controllo
 * che non torna (S20), il codice che segue o non segue la voce (S8). Il codice scritto
 * è stato di questo pannello, che nasce e muore con lui: quello di un'altra voce non
 * può restare nel campo. */
export function ScannerPanel({
  item,
  ingredientId,
  onProduct,
  onNewCode,
  onUnlinkedCode,
  onCreateByHand,
  onCancel,
}: {
  item: ShoppingItem;
  /** L'ingrediente della voce, dalla lista o abbinato in questo schermo: la guardia
   * qui sotto ci confronta il prodotto che il codice trova. */
  ingredientId: string;
  /** Il codice ha trovato un prodotto del catalogo, di questo ingrediente. */
  onProduct: (product: Product) => void;
  /** Un codice nuovo al catalogo, che si è deciso di usare: se Open Food Facts lo
   * conosce prima si chiede se è l'ingrediente della voce (S20), se no il modulo. */
  onNewCode: (code: string, suggestion: ProductSuggestion | null) => void;
  /** Il codice letto resta alla voce (S8), o se ne va (`null`). */
  onUnlinkedCode: (code: string | null) => void;
  /** «Crea il prodotto a mano»: senza fotocamera (`code` vuoto), o dopo un lookup
   * fallito (`code` letto, `lookedUp` "failed"). */
  onCreateByHand: (code: string, lookedUp?: "failed") => void;
  onCancel: () => void;
}) {
  const codeId = useId();
  const [manualCode, setManualCode] = useState("");
  const [cameraMissing, setCameraMissing] = useState(false);
  // un codice letto che porta al prodotto di un altro ingrediente: non è una
  // risoluzione, è la ragione per cui non c'è
  const [mismatch, setMismatch] = useState<Product | null>(null);
  // un codice nuovo al catalogo la cui cifra di controllo non torna: si ferma qui,
  // correggibile, finché chi l'ha letto non lo usa lo stesso
  const [badCode, setBadCode] = useState<
    { code: string; suggestion: ProductSuggestion | null } | null
  >(null);

  // Il lookup passa da una mutazione e non da una chiamata nuda per due ragioni: un
  // errore non resta una promise rifiutata che nessuno guarda (prima, con la rete giù,
  // premere Invio non faceva assolutamente niente), e un 401 passa dalla MutationCache
  // di App.tsx, cioè riporta all'accesso come ogni altra scrittura.
  const lookup = useMutation({
    mutationFn: (code: string) => lookupBarcode(code),
    // gli avvisi parlavano del codice di prima: con uno nuovo in volo non valgono più
    onMutate: () => {
      setBadCode(null);
      setMismatch(null);
    },
    onSuccess: (result, code) => {
      const product = result.product;
      // un codice che ha già il suo prodotto non segue la voce altrove, neanche
      // quando quel prodotto è di un altro ingrediente: darlo a un prodotto nuovo
      // sarebbe un 409, e a uno scelto a catalogo un furto che il backend rifiuta.
      // Uno nuovo al catalogo lo ricorda chi riceve `onNewCode`, quando si decide di
      // usarlo
      onUnlinkedCode(null);
      if (product && product.ingredient_id !== ingredientId) {
        // `GET /products/barcode/{code}` cerca per codice e basta, quindi la referenza
        // che torna può essere di un altro ingrediente. Adottarla faceva fallire con
        // 409 l'intera sistemazione — che è tutto-o-niente — comprese le voci risolte
        // bene. Il controllo del backend resta l'ultima difesa; l'interfaccia non deve
        // arrivarci.
        setMismatch(product);
        return;
      }
      // un prodotto del catalogo si aggancia anche se la cifra di controllo non torna:
      // qualcuno l'ha già confermato con la confezione in mano
      if (product) {
        onProduct(product);
        return;
      }
      if (result.valid_checksum === false) {
        // S20: `1234` apriva la creazione di un prodotto sotto un codice che nessuna
        // confezione porta. Il codice resta nel campo, correggibile — uno letto dalla
        // fotocamera ci arriva adesso — e «Usa questo codice lo stesso» lascia andare
        // avanti: i codici interni di negozio esistono.
        setBadCode({ code, suggestion: result.suggestion });
        setManualCode(code);
        return;
      }
      onNewCode(code, result.suggestion);
    },
    // il codice è stato letto anche se il lookup no: la creazione a mano lo porta, e
    // il catalogo pure (S8). Se poi risultasse di un altro prodotto, il backend non lo
    // sposta
    onError: (_error, code) => onUnlinkedCode(code),
  });
  const { mutate: lookupCode } = lookup;
  const failedCode = lookup.isError ? (lookup.variables ?? null) : null;

  // Stabili: l'effetto della fotocamera dipende da tutti e due, e un'identità nuova a
  // ogni tasto premuto nel campo la spegnerebbe e riaccenderebbe a ogni carattere.
  // `mutate` di react-query è già stabile.
  const handleDetected = useCallback((code: string) => lookupCode(code), [lookupCode]);
  const markCameraMissing = useCallback(() => setCameraMissing(true), []);

  function search() {
    const code = manualCode.trim();
    // la guardia al posto di `disabled`: il pulsante resta dov'è il fuoco
    if (code === "" || lookup.isPending) return;
    lookupCode(code);
  }

  return (
    <div className="flex flex-col gap-3 rounded-card border border-line p-3">
      {/* il nome della voce nel titolo: prima stava solo nel testo per lo screen reader
          del pulsante che apre il pannello, e arrivati qui non si sapeva più cosa si
          stava scansionando (S10) */}
      <h2 className="font-semibold">Codice a barre per «{item.raw_text}»</h2>
      <BarcodeScanner
        onDetected={handleDetected}
        onCancel={onCancel}
        onUnavailable={markCameraMissing}
      >
        <div className="flex flex-col gap-1.5">
          <label htmlFor={codeId} className="text-sm">
            Codice a barre
          </label>
          <div className="flex gap-2">
            {/* `inputMode="numeric"`: tredici cifre sulla tastiera delle lettere erano
                il secondo dettaglio di S10 */}
            <input
              id={codeId}
              inputMode="numeric"
              autoComplete="off"
              value={manualCode}
              onChange={(e) => setManualCode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  search();
                }
              }}
              className="min-w-0 flex-1"
            />
            <button
              type="button"
              aria-disabled={lookup.isPending || undefined}
              onClick={search}
              className={`${buttonClasses("secondary")} shrink-0 aria-disabled:opacity-40`}
            >
              {/* un pulsante da solo → icona e testo (spec §3.3); il nome resta «Cerca» */}
              <IconSearch aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
              Cerca
            </button>
          </div>
        </div>

        {lookup.isPending && <p className="text-sm text-ink-soft">Cerco il codice…</p>}

        {/* il codice esiste in catalogo, ma sotto un altro ingrediente: si dice quale,
            e non in rosso — non è un guasto (spec T3 §4.3). Nessuna risoluzione: le tre
            icone della voce sono ancora là sopra.
            La cornice `role="status"` sta nel DOM anche vuota (regola F9): uno screen
            reader annuncia il cambiamento di un nodo che era già lì, non uno appena
            arrivato insieme al testo — è il testo che entra ed esce da dentro. Vuota
            resta nell'albero dell'accessibilità (niente `hidden`), ma `empty:-mt-3`
            ne ripaga lo spazio: senza, la colonna mette due distanze di 12 px dove ne
            va una. */}
        <p role="status" className="text-sm text-ink empty:-mt-3">
          {mismatch && (
            <>
              {otherIngredient(mismatch.name, mismatch.ingredient_name)} Qui non si aggancia:
              leggi un altro codice, cercalo a catalogo, oppure conferma «{item.raw_text}» come
              sfuso.
            </>
          )}
        </p>

        {badCode && (
          <div className="flex flex-col items-start gap-2">
            <Alert>Questo codice non torna: ricontrollalo.</Alert>
            <Button onClick={() => onNewCode(badCode.code, badCode.suggestion)}>
              Usa questo codice lo stesso
            </Button>
          </div>
        )}

        {/* anche il fallimento di rete degrada al manuale: un errore muto qui era il
            muro più silenzioso dello schermo */}
        {failedCode !== null && (
          <p role="alert" className="text-sm text-danger">
            Non sono riuscito a leggere il codice. Riprova, oppure crea il prodotto a mano.
          </p>
        )}

        {/* senza fotocamera il pannello prometteva «Puoi inserire il prodotto a mano» e
            non offriva quella strada (S10). Un pulsante solo anche a lookup fallito: lì
            porta il codice che non si è potuto cercare */}
        {(cameraMissing || failedCode !== null) && (
          <Button
            icon={IconPencilPlus}
            onClick={() =>
              onCreateByHand(failedCode ?? "", failedCode !== null ? "failed" : undefined)
            }
            className="self-start"
          >
            Crea il prodotto a mano
          </Button>
        )}
      </BarcodeScanner>
    </div>
  );
}
