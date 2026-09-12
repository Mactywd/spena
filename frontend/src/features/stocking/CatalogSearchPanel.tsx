import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchProducts } from "./api";
import { OTHER_INGREDIENT } from "./wording";
import { useDebounced } from "../../hooks/useDebounced";
import type { Product } from "../../domain/types";
import { buttonClasses } from "../../components/ui/buttonClasses";

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
 * parole a quello che si è già scritto.
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
  // parte dal testo della voce, come dice la spec §8.2 («da `yogurt greco` a
  // `yogurt greco carrefour pesca`»): affinare è aggiungere parole a quel che si è
  // già scritto. Vale quando il nome del prodotto contiene il termine generico, che
  // è il caso di Open Food Facts; per una referenza di sola marca il campo si
  // riscrive, ed è il motivo per cui non è di sola lettura.
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
  const elsewhere = found.length - mine.length;
  const nothingToPick = isSuccess && mine.length === 0;

  return (
    <div className="mt-4 flex flex-col gap-3 rounded-card bg-card p-4">
      <h3 className="font-semibold">Cerca a catalogo per «{itemLabel}»</h3>
      <label className="text-sm">
        Nome del prodotto
        <input
          aria-label="Cerca a catalogo"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          className="mt-1.5"
        />
      </label>
      <p className="text-xs text-ink-soft">
        Aggiungi parole per restringere: «yogurt greco», poi «yogurt greco pesca».
      </p>

      {mine.length > 0 && (
        <ul role="listbox" className="divide-y divide-line overflow-hidden rounded-card bg-card">
          {mine.map((product) => (
            <li key={product.id}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => onPicked(product)}
                className="min-h-11 w-full px-3 py-3 text-left text-sm"
              >
                {/* lo spazio esplicito: senza, il nome accessibile del pulsante è
                    "Total 0%Fage", che è quello che legge uno screen reader */}
                {product.name}{" "}
                {product.brand && (
                  <span className="text-xs text-ink-soft">{product.brand}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* perché un prodotto che esiste può non comparire: senza questa riga
          sembrerebbe che il catalogo non lo conosca */}
      {elsewhere > 0 && (
        <p className="text-xs text-ink-soft">
          {elsewhere === 1
            ? `Un altro prodotto corrisponde, ma ${OTHER_INGREDIENT.one}.`
            : `Altri ${elsewhere} prodotti corrispondono, ma ${OTHER_INGREDIENT.many}.`}
        </p>
      )}

      {/* "con queste parole", non "in catalogo": la ricerca guarda nome e marca del
          prodotto, e il campo parte dal testo della voce di lista, che per una
          referenza di marca può non comparire da nessuna parte — «Total 0% Fage»
          non contiene «yogurt greco». Dire che il catalogo è vuoto sarebbe un
          verdetto sbagliato sulla prima schermata del pannello. */}
      {nothingToPick && (
        <p className="text-sm text-ink-soft">
          Nessun prodotto con queste parole: la ricerca guarda nome e marca, prova con la
          marca. Oppure crealo adesso, leggi il codice a barre, o conferma la voce come sfusa.
        </p>
      )}

      {/* anche qui la rete può essere giù, e il catalogo è solo una delle tre
          strade: dirlo senza togliere le altre */}
      {isError && (
        <p role="alert" className="text-sm text-danger">
          La ricerca a catalogo non risponde. Riprova, oppure crea il prodotto a mano.
        </p>
      )}

      {(nothingToPick || isError) && (
        <button
          type="button"
          onClick={onCreateByHand}
          className={`${buttonClasses("secondary")} self-start`}
        >
          Crea il prodotto a mano
        </button>
      )}

      <button
        type="button"
        onClick={onCancel}
        className={`${buttonClasses("ghost")} self-start`}
      >
        Annulla
      </button>
    </div>
  );
}
