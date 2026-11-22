import { useEffect, useId, useRef } from "react";
import { Button } from "../../components/ui/Button";
import { IconCalendarPlus, IconX } from "../../components/ui/icons";
import { EXPIRY_INPUT_MAX } from "../pantry/expiryLabels";

/** La scadenza di una confezione che sta per entrare in dispensa (S7, D5): dietro
 * «+ scadenza», un campo data nativo con la sua ✕. Dietro un tocco, sempre: dieci campi
 * vuoti sarebbero rumore permanente sullo schermo più denso dell'app, per chi la
 * scadenza non la scrive mai.
 *
 * Estratta da StockingRow (S3): la usano la riga di «Sistema la spesa», le confezioni in
 * più di una voce e la scheda di conferma della Dispensa, e le sue guardie del fuoco
 * devono restare una. Il valore lo tiene chi la usa: la riga può rinascere mentre il
 * campo è aperto, e la data scritta non deve sparire con lei. */
export function ExpiryField({
  name,
  value,
  onChange,
}: {
  /** Di che cosa: entra nei nomi per chi ascolta («Scadenza di mele»). */
  name: string;
  /** `undefined`: il campo è chiuso. Una stringa, anche vuota: è aperto. */
  value: string | undefined;
  /** `""` apre il campo, una data la scrive, `undefined` lo chiude svuotandolo. */
  onChange: (value: string | undefined) => void;
}) {
  const expiryButton = useRef<HTMLButtonElement>(null);
  // la ✕ ed Esc chiudono il campo: il fuoco torna a «+ scadenza» invece di cadere sul
  // `body` insieme al campo che sparisce
  const refocusExpiry = useRef(false);
  // «+ scadenza» porta il fuoco nel campo. Non `autoFocus`: la riga rinasce a ogni
  // pannello aperto o chiuso (decisione 21, il campo resta aperto), e a ogni rinascita il
  // campo si riprendeva il fuoco — quello di «Annulla» finiva nella data di un'altra voce
  // invece che sul pulsante che aveva aperto il pannello (misurato nell'e2e). Solo il
  // tocco lo chiede, e un campo appena nato non l'ha avuto
  const expiryInput = useRef<HTMLInputElement>(null);
  const focusExpiryInput = useRef(false);
  const expiryId = useId();
  const open = value !== undefined;

  useEffect(() => {
    if (!open && refocusExpiry.current) {
      refocusExpiry.current = false;
      expiryButton.current?.focus();
    }
    if (open && focusExpiryInput.current) {
      focusExpiryInput.current = false;
      expiryInput.current?.focus();
    }
  }, [open]);

  function close() {
    refocusExpiry.current = true;
    onChange(undefined);
  }

  return open ? (
    <div className="flex items-end gap-1 pb-1">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        {/* un'etichetta che si vede (dal giro): prima era solo per lo screen reader */}
        <label htmlFor={expiryId} className="text-xs text-ink-soft">
          Scadenza <span className="sr-only">di {name}</span>
        </label>
        <input
          ref={expiryInput}
          id={expiryId}
          type="date"
          max={EXPIRY_INPUT_MAX}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              // la data si manda con «Metti in dispensa», non c'è niente da
              // confermare; e senza `preventDefault` l'Invio arrivava al pulsante che
              // riprendeva il fuoco (la lezione della Consegna 1)
              e.preventDefault();
            } else if (e.key === "Escape") {
              e.preventDefault();
              close();
            }
          }}
        />
      </div>
      <Button
        variant="ghost"
        icon={IconX}
        label={`Togli la data di scadenza per ${name}`}
        onClick={close}
      />
    </div>
  ) : (
    <button
      ref={expiryButton}
      type="button"
      onClick={() => {
        focusExpiryInput.current = true;
        onChange("");
      }}
      className="flex min-h-11 items-center gap-1 text-xs font-medium text-ink-faint"
    >
      <IconCalendarPlus aria-hidden="true" className="size-4" stroke={1.8} />
      {/* qui lo `sr-only` resta: «+ scadenza» da solo non dice di quale voce, e il
          nome per {name} serve solo a chi ascolta. Lo spazio prima sta fuori dallo
          `sr-only`, non dentro: dentro, Chromium lo mangia insieme al resto del testo
          nascosto e «+ scadenza per X» arriva allo screen reader come «+ scadenzaper
          X», appiccicati */}
      + scadenza <span className="sr-only">per {name}</span>
    </button>
  );
}
