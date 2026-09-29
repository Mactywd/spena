import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchProducts } from "./api";
import { elsewhereNote } from "./wording";
import { useDebounced } from "../../hooks/useDebounced";
import { Button } from "../../components/ui/Button";
import { IconPencilPlus } from "../../components/ui/icons";
import type { Product } from "../../domain/types";

const DEBOUNCE_MS = 180;

/**
 * La seconda delle tre strade della spec §8.2: «ricerca a catalogo per nome con
 * affinamento progressivo — da `yogurt greco` a `yogurt greco carrefour pesca`
 * finché non compare la referenza giusta». Serve per il prodotto che si ricompra
 * ogni settimana: è già in catalogo con marca e nutrienti, e senza questa strada
 * l'unico modo di riagganciarlo è riscansionare il codice a barre — che non si può
 * fare se la confezione è già aperta, se il codice è rovinato o se la fotocamera
 * non c'è. L'alternativa, «sfuso», perde la marca e con essa i nutrienti.
 *
 * Il campo parte dal testo della voce di lista, perché l'affinamento è aggiungere
 * parole a quello che si è già scritto (dal giro di T3: da non riprogettare via).
 *
 * Un messaggio per stato (T3 Consegna 3): «altri 2 prodotti, di un altro ingrediente»
 * e «nessun prodotto» a video insieme si contraddicevano, e l'esempio «yogurt greco»
 * compariva anche cercando le uova.
 */
export function CatalogSearchPanel({
  itemLabel,
  ingredientId,
  onPicked,
  onCreateByHand,
  onCancel,
}: {
  itemLabel: string;
  /** L'ingrediente della voce di lista. Filtra i risultati, e non per estetica:
   * `add_pantry_item` (app/repositories/pantry.py) respinge con 409 la coppia
   * (ingrediente, prodotto) incoerente, e la sistemazione è tutto-o-niente —
   * quindi una scelta sbagliata accettata qui farebbe fallire l'intero giro di
   * spesa, comprese le voci risolte bene. Rifiutare dopo aver confermato è
   * peggio che non offrire una scelta che non si può accettare. */
  ingredientId: string;
  onPicked: (product: Product) => void;
  onCreateByHand: () => void;
  onCancel: () => void;
}) {
  const [term, setTerm] = useState(itemLabel);
  const debounced = useDebounced(term, DEBOUNCE_MS).trim();
  const ready = debounced.length >= 2;

  // come ogni altra ricerca dell'app: la chiave porta il termine, quindi una
  // risposta superata non può sovrascrivere una più recente, e un 401 arriva alla
  // QueryCache che riporta all'accesso
  const { data: found = [], isError, isSuccess } = useQuery({
    queryKey: ["products", debounced],
    queryFn: () => searchProducts(debounced),
    enabled: ready,
  });

  const mine = found.filter((product) => product.ingredient_id === ingredientId);
  // di chi sono gli altri: lo dice il server (`ingredient_name`), il client non va a
  // cercarselo
  const elsewhere = found
    .filter((product) => product.ingredient_id !== ingredientId)
    .map((product) => product.ingredient_name);

  // `term` e non `debounced` per l'esempio: svuotato il campo, l'invito compare subito
  const state: "hint" | "searching" | "failed" | "found" | "elsewhere" | "none" =
    term.trim().length < 2
      ? "hint"
      : isError
        ? "failed"
        : !isSuccess
          ? "searching"
          : mine.length > 0
            ? "found"
            : elsewhere.length > 0
              ? "elsewhere"
              : "none";

  return (
    <div className="flex flex-col gap-3 rounded-card border border-line p-3">
      <h2 className="font-semibold">Cerca a catalogo per «{itemLabel}»</h2>
      <label className="text-sm">
        Nome o marca del prodotto
        <input
          aria-label="Cerca a catalogo"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          className="mt-1.5"
        />
      </label>

      {state === "hint" && (
        <p className="text-sm text-ink-soft">
          Scrivi il nome o la marca, poi aggiungi parole per restringere: «yogurt greco», poi
          «yogurt greco pesca».
        </p>
      )}

      {state === "searching" && <p className="text-sm text-ink-soft">Cerco…</p>}

      {state === "found" && (
        <>
          {/* un listbox contiene opzioni e basta: niente `<ul>/<li>` in mezzo, come in
              OptionList (dal giro di T3) */}
          <div
            role="listbox"
            aria-label={`Prodotti per «${itemLabel}»`}
            className="flex flex-col overflow-hidden rounded-card ring-1 ring-line ring-inset"
          >
            {mine.map((product) => (
              <button
                key={product.id}
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => onPicked(product)}
                className="flex min-h-11 w-full items-baseline gap-2 px-3 py-2.5 text-left text-sm"
              >
                {/* lo spazio esplicito: senza, il nome accessibile del pulsante è
                    "Total 0%Fage", che è quello che legge uno screen reader */}
                <span>{product.name}</span>{" "}
                {product.brand && <span className="text-xs text-ink-soft">{product.brand}</span>}
              </button>
            ))}
          </div>
          {/* perché un prodotto che esiste può non comparire: senza questa riga
              sembrerebbe che il catalogo non lo conosca */}
          {elsewhere.length > 0 && (
            <p className="text-xs text-ink-soft">{elsewhereNote(elsewhere)}</p>
          )}
        </>
      )}

      {state === "elsewhere" && (
        <p className="text-sm text-ink-soft">
          {elsewhereNote(elsewhere)} Per questa voce prova con la marca, oppure crealo adesso.
        </p>
      )}

      {/* "con queste parole", non "in catalogo": la ricerca guarda nome e marca del
          prodotto, e il campo parte dal testo della voce di lista, che per una
          referenza di marca può non comparire da nessuna parte — «Total 0% Fage»
          non contiene «yogurt greco». Dire che il catalogo è vuoto sarebbe un
          verdetto sbagliato sulla prima schermata del pannello. */}
      {state === "none" && (
        <p className="text-sm text-ink-soft">
          Nessun prodotto con queste parole: la ricerca guarda nome e marca, prova con la
          marca. Oppure crealo adesso, leggi il codice a barre, o conferma la voce come sfusa.
        </p>
      )}

      {/* anche qui la rete può essere giù, e il catalogo è solo una delle tre
          strade: dirlo senza togliere le altre */}
      {state === "failed" && (
        <p role="alert" className="text-sm text-danger">
          La ricerca a catalogo non risponde. Riprova, oppure crea il prodotto a mano.
        </p>
      )}

      {(state === "none" || state === "elsewhere" || state === "failed") && (
        <Button icon={IconPencilPlus} onClick={onCreateByHand} className="self-start">
          Crea il prodotto a mano
        </Button>
      )}

      <Button variant="ghost" onClick={onCancel} className="self-start">
        Annulla
      </Button>
    </div>
  );
}
