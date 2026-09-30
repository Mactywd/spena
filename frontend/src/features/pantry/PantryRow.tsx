import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { StockGauge } from "../../components/ui/StockGauge";
import { IconListCheck, IconShoppingCartPlus, IconX } from "../../components/ui/icons";
import { EXPIRY_INPUT_MAX, expiryText } from "./expiryLabels";
import { itemLabel } from "./pantryView";
import { ingredientPath, productPath } from "../registry/origin";
import { revealAtTop } from "../../lib/revealAtTop";
import { capitalizeFirst } from "../../lib/text";
import type { PantryItem, PantryStatus } from "../../domain/types";

/** Dove porta il nome: alla scheda del prodotto se la voce ne ha uno, a quella
 * dell'ingrediente se è sfusa (spec S9 §6.5). */
function registryPath(item: PantryItem): string {
  return item.product_id
    ? productPath(item.product_id, "dispensa")
    : ingredientPath(item.ingredient_id, "dispensa");
}

const EXPIRY_TONE_TEXT = {
  soon: "font-medium text-expiry",
  expired: "font-semibold text-expiry",
} as const;

/** Una riga della dispensa (spec T3 §4.1): l'ingrediente, sotto il prodotto, a
 * destra le tacche e la ✕; sotto ancora, su una riga sua, la scadenza. Il nome è l'ingrediente e non il prodotto
 * (dal giro): così un aggancio sbagliato, il parmigiano sotto «burro», si vede proprio
 * qui, dove si corregge (S9). */
export function PantryRow({
  item,
  busy,
  failed,
  listed,
  reveal,
  onStatus,
  onRemove,
  onRestock,
  onExpiry,
  onRevealed,
}: {
  item: PantryItem;
  busy: boolean;
  failed: boolean;
  listed: boolean;
  reveal: boolean;
  onStatus: (status: PantryStatus) => void;
  onRemove: () => void;
  onRestock: () => void;
  onExpiry: (expiresOn: string | null) => Promise<unknown>;
  onRevealed: () => void;
}) {
  const label = itemLabel(item);
  const [editingExpiry, setEditingExpiry] = useState(false);
  const ref = useRef<HTMLLIElement>(null);
  const expiryButton = useRef<HTMLButtonElement>(null);
  // Esc chiude il campo senza scrivere. Se un browser mandasse un blur mentre il
  // campo sparisce col fuoco dentro, troverebbe questo segno e non salverebbe: è una
  // guardia difensiva — la specifica non prevede quel blur, e React non lo vedrebbe
  // su un nodo già staccato — e nessun test la esercita. Si azzera a ogni apertura.
  const expiryCancelled = useRef(false);
  // Invio ed Esc chiudono il campo dalla tastiera: il fuoco torna al pulsante della
  // scadenza invece di cadere sul `body`. Un tocco altrove no — lì il fuoco va dove
  // si è toccato, e riprenderselo sarebbe un furto.
  const refocusExpiry = useRef(false);

  useEffect(() => {
    if (!editingExpiry && refocusExpiry.current) {
      refocusExpiry.current = false;
      expiryButton.current?.focus();
    }
  }, [editingExpiry]);

  useEffect(() => {
    if (reveal && ref.current) {
      revealAtTop(ref.current);
      onRevealed();
    }
  }, [reveal, onRevealed]);

  // Si scrive all'uscita dal campo, non a ogni battuta, e non è una preferenza.
  // Un `input[type="date"]` non fa scattare `change` una volta alla fine: lo fa a
  // ogni segmento toccato. Misurato in Chromium, correggere l'anno di «2026-09-28»
  // battendo «2027» produce «0002-09-28», «0020-09-28», «0202-09-28», «2027-09-28»:
  // legato al `change`, il primo di quei quattro chiudeva il campo sotto le dita e
  // salvava una data dell'anno 2, che il server giudicava scaduta. Restava solo il
  // calendario nativo, ed è la ragione per cui l'e2e non l'aveva mai visto —
  // `fill()` di Playwright scrive il valore in un colpo solo. Il campo è per questo
  // non controllato (`defaultValue`): i valori di passaggio non devono risalire da
  // nessuna parte, devono solo restare nel campo finché l'utente non ha finito.
  //
  // Il campo chiude qui e non quando la richiesta torna: la lettura successiva
  // arriva da `item` (invalidato in caso di successo), e un fallimento lo dice già
  // l'`Alert` qui sotto — non serve tenere il campo aperto per mostrarlo.
  async function commitExpiry(value: string) {
    setEditingExpiry(false);
    if (expiryCancelled.current) return;
    if (value === (item.expires_on ?? "")) return;
    try {
      await onExpiry(value || null);
    } catch {
      // il guasto lo mostra già l'`Alert` della riga
    }
  }

  const expiry = item.expires_on ? expiryText(item.expires_on, item.expiry) : null;

  return (
    // `scroll-mt-16`: l'intestazione fissa (h-12) più un respiro, come nel dettaglio ricetta
    <li ref={ref} className="scroll-mt-16">
      <div className="flex items-center gap-1">
        {/* Il prodotto sta su una riga sola, tagliato coi puntini: accanto alle tacche
            restano 135px a 375px di larghezza, e i nomi veri («Deodorante per Ambienti
            Vaniglia e Gelsomino») andavano a capo fino a tre righe, con la scadenza
            spinta sotto e il «·» rimasto solo. Il nome intero è nella scheda del
            prodotto, dove porta il link. */}
        <div className="min-w-0 flex-1">
          {/* la maiuscola solo a video (spec T3 §4.7): i nomi accessibili dei controlli
              della riga usano `label`, in mezzo a una frase, e restano com'è */}
          <Link
            to={registryPath(item)}
            className="flex min-h-11 items-end pb-0.5 font-medium underline decoration-line underline-offset-4"
          >
            {capitalizeFirst(item.ingredient_name)}
          </Link>
          <p className="truncate pt-0.5 text-xs text-ink-faint">{item.product_name ?? "sfuso"}</p>
        </div>
        <StockGauge status={item.status} itemName={label} disabled={busy} onChange={onStatus} />
        <Button
          variant="ghost"
          icon={IconX}
          label={`Togli ${label} dalla dispensa`}
          onClick={onRemove}
          busy={busy}
        />
      </div>
      {/* La scadenza ha la sua riga, larga quanto la voce: sempre allo stesso posto, e
          il campo data ha lo spazio che accanto alle tacche non avrebbe. */}
      <div className="flex min-h-11 items-start text-xs text-ink-faint">
        {editingExpiry ? (
          <span className="pt-0.5">
            <label htmlFor={`expiry-${item.id}`} className="sr-only">
              Scadenza di {label}
            </label>
            <input
              id={`expiry-${item.id}`}
              type="date"
              max={EXPIRY_INPUT_MAX}
              disabled={busy}
              autoFocus
              defaultValue={item.expires_on ?? ""}
              onBlur={(event) => void commitExpiry(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  // senza, l'Invio arriva anche al pulsante che riprende il fuoco qui
                  // sotto, e lo «preme»: il campo si riapriva con la data di prima
                  event.preventDefault();
                  refocusExpiry.current = true;
                  event.currentTarget.blur();
                } else if (event.key === "Escape") {
                  event.preventDefault();
                  expiryCancelled.current = true;
                  refocusExpiry.current = true;
                  setEditingExpiry(false);
                }
              }}
            />
          </span>
        ) : (
          <button
            ref={expiryButton}
            type="button"
            // `aria-disabled` e non `disabled`, come le tacche: dopo un Invio il fuoco
            // torna qui mentre il salvataggio è in volo, e il browser toglie il fuoco a
            // un pulsante che diventa `disabled` — finiva sul `body`
            aria-disabled={busy || undefined}
            onClick={() => {
              if (busy) return;
              expiryCancelled.current = false;
              setEditingExpiry(true);
            }}
            aria-label={expiry ? `Scadenza di ${label}: ${expiry}` : `+ scadenza per ${label}`}
            className={`flex min-h-11 items-start pt-0.5 text-left aria-disabled:opacity-40 ${
              item.expiry ? EXPIRY_TONE_TEXT[item.expiry] : ""
            }`}
          >
            {expiry ?? "+ scadenza"}
          </button>
        )}
      </div>
      {item.status === "finished" && (
        // «Lo rimetto in lista? Sì / No» aveva bersagli da 35px e non tornava più se
        // ignorato: ora è un pulsante che resta finché serve, e ignorarlo è il «No»
        <div className="flex items-center justify-between gap-2 pb-2">
          <span className="text-sm font-medium text-finished">Finito</span>
          {listed ? (
            <span className="flex items-center gap-1 text-sm text-ink-soft">
              <IconListCheck aria-hidden="true" className="size-4" stroke={1.8} />
              Già in lista
            </span>
          ) : (
            <Button icon={IconShoppingCartPlus} onClick={onRestock} busy={busy}>
              In lista
            </Button>
          )}
        </div>
      )}
      {failed && <Alert className="pb-2">Non sono riuscito a salvare la modifica. Riprova.</Alert>}
    </li>
  );
}
