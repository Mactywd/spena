import { useEffect, useRef } from "react";
import { entryTitle, type EntryChoice } from "./entryView";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { IconToolbar } from "../../components/ui/IconToolbar";
import {
  IconBarcode,
  IconListSearch,
  IconPackageImport,
  IconReplace,
} from "../../components/ui/icons";
import { ExpiryField } from "../stocking/ExpiryField";

/** La scheda di conferma dell'ingresso diretto (S3 §4.4, decisa da Mattia il
 * 2026-10-07): un tocco in più prima di scrivere, perché un codice letto male o un
 * prodotto agganciato all'ingrediente sbagliato non finiscano in dispensa in silenzio
 * (S13), e perché è il solo posto dove la scadenza si scrive con la confezione in mano
 * (D5). Dice cosa entra; «Metti in dispensa» è il primario e prende il fuoco: dopo la
 * lettura del codice, è il secondo e ultimo tocco. */
export function EntryCard({
  choice,
  expiry,
  onExpiry,
  busy,
  failed,
  justEntered,
  onCode,
  onCatalog,
  onChange,
  onConfirm,
  onCancel,
}: {
  choice: EntryChoice;
  expiry: string | undefined;
  onExpiry: (value: string | undefined) => void;
  /** La scrittura è in volo: il pulsante si spegne ma tiene il fuoco. */
  busy: boolean;
  failed: boolean;
  /** Lo stesso prodotto è appena entrato, in questa serie: lo si dice, invece di
   * scriverlo due volte in silenzio (S3 §4.5). Due confezioni uguali esistono: si può
   * mettere lo stesso. */
  justEntered: boolean;
  /** Dal +, a scheda sfusa: le altre due strade della sistemazione, con la marca. */
  onCode?: () => void;
  onCatalog?: () => void;
  onChange: () => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  // il fuoco su «Metti in dispensa» appena la scheda compare: chi l'ha aperta ha appena
  // letto un codice o scelto un ingrediente, e il pulsante che aveva il fuoco è sparito
  useEffect(() => {
    confirmRef.current?.focus();
  }, []);

  const title = entryTitle(choice);
  const { product } = choice;
  const detail = product
    ? [product.brand, choice.ingredient.name].filter(Boolean).join(" · ")
    : `Sfuso, senza marca · ${choice.ingredient.name}`;

  return (
    <div className="flex flex-col gap-2 rounded-card border border-line p-3">
      <div className="flex items-start gap-2">
        {/* `min-w-0` e `break-words`: il nome di un prodotto può essere lungo, e a 375px
            non deve spingere «Cambia» fuori dallo schermo */}
        <div className="min-w-0 flex-1 break-words">
          <p className="font-medium">{title}</p>
          <p className="text-xs text-ink-soft">{detail}</p>
        </div>
        <Button variant="ghost" icon={IconReplace} label={`Cambia: ${title}`} onClick={onChange} />
      </div>

      {onCode && onCatalog && (
        <div className="flex items-center gap-2">
          <p className="text-xs text-ink-soft">Con la marca:</p>
          <IconToolbar label={`Con la marca: ${title}`}>
            <Button
              variant="ghost"
              icon={IconBarcode}
              label={`Codice a barre per ${title}`}
              onClick={onCode}
            />
            <Button
              variant="ghost"
              icon={IconListSearch}
              label={`Cerca a catalogo per ${title}`}
              onClick={onCatalog}
            />
          </IconToolbar>
        </div>
      )}

      {justEntered && (
        <p className="text-sm text-ink">
          L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.
        </p>
      )}

      <ExpiryField name={title} value={expiry} onChange={onExpiry} />

      {/* accanto al pulsante che ha fallito, e niente si perde: la scelta e la data
          restano, e «Metti in dispensa» si ritocca */}
      {failed && <Alert>Non sono riuscito ad aggiungere la voce in dispensa. Riprova.</Alert>}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          ref={confirmRef}
          variant="primary"
          icon={IconPackageImport}
          busy={busy}
          onClick={onConfirm}
        >
          Metti in dispensa
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Annulla
        </Button>
      </div>
    </div>
  );
}
