import { useEffect, useRef, useState } from "react";
import { LOW_MAX_FILL } from "./fillZones";

// Le tre zone dipinte sulla traccia. I colori sono token (`var(--color-…)`), non
// valori grezzi: il rosso è lo stesso di ogni rifiuto, l'ambra lo stesso di «quasi
// finito», il verde lo stesso del marchio. Il primo tratto è corto di proposito —
// lo zero è un punto, non una zona in cui si atterra per caso.
//
// Il verde comincia a `LOW_MAX_FILL + 1`, non a `LOW_MAX_FILL`: `status_for_fill`
// in backend/app/domain/rules.py dice `<= LOW_MAX_FILL` è ancora `low`, quindi 30
// deve cadere nel giallo. Attaccare il verde esattamente a 30 metterebbe la cucitura
// fra i due colori proprio sul valore che, col passo di 5, il cursore raggiunge —
// e la pastiglia accanto direbbe ancora «Quasi finito» su un pallino già verde.
const ZONES =
  "linear-gradient(to right," +
  " var(--color-danger) 0 3%," +
  ` var(--color-low-tint) 3% ${LOW_MAX_FILL + 1}%,` +
  ` var(--color-brand-tint) ${LOW_MAX_FILL + 1}% 100%)`;

/** Quanto ne resta, a occhio.
 *
 * Il valore si scrive quando il dito si alza, non a ogni scatto: una PATCH ogni
 * pochi millisecondi arriverebbe fuori ordine e l'ultima a rispondere vincerebbe.
 * Lo stato non si calcola qui — lo ricava il backend e lo mostra la pastiglia
 * accanto, che è l'unica cosa in questa riga a dire una verità.
 */
export function FillSlider({
  value,
  label,
  disabled = false,
  onCommit,
}: {
  value: number;
  /** che cosa si sta misurando: entra nel nome accessibile del cursore */
  label: string;
  disabled?: boolean;
  onCommit: (percent: number) => void;
}) {
  const [position, setPosition] = useState(value);
  // l'ultima posizione già inviata, non la verità del server: `value` cambia solo
  // al refetch, che arriva dopo. Confrontare con `value` (com'era) lascia una
  // finestra in cui un secondo evento — un'altra riga toccata, un Tab — rilancia
  // in silenzio la stessa scrittura una seconda volta.
  const sent = useRef(value);

  // quando la verità cambia da fuori — l'annulla, una ricarica, una cottura — è
  // quella a comandare, non dove il dito aveva lasciato il cursore
  useEffect(() => {
    setPosition(value);
    sent.current = value;
  }, [value]);

  const commit = () => {
    if (position !== sent.current) {
      sent.current = position;
      onCommit(position);
    }
  };

  return (
    <div className="relative flex h-11 items-center">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 h-2 rounded-full"
        style={{ backgroundImage: ZONES }}
      />
      <input
        type="range"
        min={0}
        max={100}
        step={5}
        value={position}
        disabled={disabled}
        aria-label={`Quanto ne resta di ${label}`}
        onChange={(event) => setPosition(Number(event.target.value))}
        onPointerUp={commit}
        onKeyUp={commit}
        onBlur={commit}
        className="relative h-11 w-full appearance-none bg-transparent disabled:opacity-50"
      />
    </div>
  );
}
