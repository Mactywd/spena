import { useEffect, useRef, useState, type PointerEvent } from "react";
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

const STEP = 5;

// Il diametro del pallino, in px: lo stesso `1.75rem` di `input[type="range"]::…-thumb`
// in src/index.css. Serve per leggere un tocco come fa il browser: il centro del
// pallino corre da mezzo pallino dopo il bordo sinistro a mezzo pallino prima del
// destro, e un tocco sul pallino deve valere il valore che il pallino mostra.
const THUMB_PX = 28;

// Quanto si può muovere il dito fra appoggio e sollievo restando un tocco. Un dito
// che si posa e si alza trema di qualche pixel; un dito che scorre la pagina ne
// percorre decine. 10px sta fra i due, e ha l'ordine di grandezza della soglia con
// cui Android stesso separa un tocco da uno scorrimento (8dp).
const TAP_TOLERANCE_PX = 10;

/** Il valore sotto un punto del cursore, sul passo del cursore. */
function percentAt(clientX: number, rect: DOMRect): number {
  const run = rect.width - THUMB_PX;
  if (run <= 0) return 0;
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left - THUMB_PX / 2) / run));
  return Math.round((ratio * 100) / STEP) * STEP;
}

/** Quanto ne resta, a occhio.
 *
 * Col dito il cursore si cambia solo toccando: il dito si posa e si alza nello
 * stesso punto, e il pallino va lì. Trascinare non cambia niente. È la regola del
 * difetto S13: la dispensa è una colonna di cursori, e scorrerla con un pollice
 * che parte da uno di loro lo spostava e poi lo scriveva al sollevarsi — uno stato
 * sbagliato in dispensa, messo lì senza che nessuno lo avesse chiesto. Per questo
 * l'`<input>` nativo non riceve eventi del puntatore (`pointer-events-none`): il suo
 * trascinamento non esiste più, e i gesti li legge il contenitore. `touch-manipulation`
 * lascia al browser ogni scorrimento e anche lo zoom a due dita (che `pan-y` avrebbe
 * tolto a chi ne ha bisogno per leggere), togliendo solo il doppio tocco per
 * ingrandire, che su una colonna di bersagli da toccare è un incidente. Il mouse
 * segue la stessa regola: un clic sposta il pallino, un trascinamento no — due
 * comportamenti per lo stesso controllo sarebbero una cosa in più da sapere, per
 * niente.
 *
 * L'`<input type="range">` resta: è lui ad avere il ruolo di cursore, il nome, il
 * valore letto a voce e le frecce della tastiera, che funzionano come prima.
 *
 * Il valore si scrive una volta per gesto — al sollevarsi del dito, o del tasto —
 * mai a ogni scatto: una PATCH ogni pochi millisecondi arriverebbe fuori ordine e
 * l'ultima a rispondere vincerebbe. Lo stato non si calcola qui — lo ricava il
 * backend e lo mostra la pastiglia accanto, che è l'unica cosa in questa riga a
 * dire una verità.
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
  // quando la verità cambia da fuori — l'annulla, una ricarica, una cottura — è
  // quella a comandare, non dove la tastiera aveva lasciato il cursore. Si
  // riallinea durante il disegno e non in un effetto: un effetto disegnerebbe
  // prima la posizione vecchia, e poi di nuovo.
  const [seen, setSeen] = useState(value);
  if (value !== seen) {
    setSeen(value);
    setPosition(value);
  }
  // l'ultima posizione già inviata, non la verità del server: `value` cambia solo
  // al refetch, che arriva dopo. Confrontare con `value` (com'era) lascia una
  // finestra in cui un secondo evento — un'altra riga toccata, un Tab — rilancia
  // in silenzio la stessa scrittura una seconda volta.
  const sent = useRef(value);
  useEffect(() => {
    sent.current = value;
  }, [value]);

  const input = useRef<HTMLInputElement>(null);
  // il gesto in corso: dove si è posato il dito, e se si è già allontanato oltre
  // la tolleranza. Un ref e non uno stato: niente di questo va disegnato.
  const press = useRef<{ id: number; x: number; y: number; dragged: boolean } | null>(null);

  const commit = (percent: number) => {
    if (percent !== sent.current) {
      sent.current = percent;
      onCommit(percent);
    }
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    // un secondo dito (lo zoom a due dita) non è un tocco, e annulla il primo
    if (press.current) {
      press.current = null;
      return;
    }
    if (disabled || !event.isPrimary || event.button !== 0) return;
    press.current = { id: event.pointerId, x: event.clientX, y: event.clientY, dragged: false };
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const p = press.current;
    if (!p || p.id !== event.pointerId) return;
    // si misura il tragitto, non solo l'arrivo: un dito che scorre e torna
    // indietro prima di alzarsi ha trascinato
    if (Math.hypot(event.clientX - p.x, event.clientY - p.y) > TAP_TOLERANCE_PX) {
      p.dragged = true;
    }
  };

  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    const p = press.current;
    press.current = null;
    if (!p || p.id !== event.pointerId || disabled) return;
    if (p.dragged || Math.hypot(event.clientX - p.x, event.clientY - p.y) > TAP_TOLERANCE_PX) {
      return;
    }
    const el = input.current;
    if (!el) return;
    // conta dove il dito si è posato, cioè dove l'utente ha mirato: il sollevarsi
    // porta con sé il tremolio
    const percent = percentAt(p.x, el.getBoundingClientRect());
    setPosition(percent);
    commit(percent);
    // col mouse il fuoco lo prendeva l'input nativo al clic; ora che non riceve il
    // puntatore glielo si dà a mano, così le frecce continuano a partire da qui.
    // Un fuoco dato da codice Chromium lo disegna con l'anello della tastiera
    // (misurato): `focusVisible: false` lo evita dove è capito, e dove non lo è
    // resta un anello su un computer, non un difetto. Col dito il fuoco non si dà
    // affatto: su un telefono non ci sono frecce, e l'anello comparirebbe attorno a
    // ogni cursore toccato.
    if (event.pointerType === "mouse") el.focus({ preventScroll: true, focusVisible: false });
  };

  // `pointercancel` è il browser che si prende il gesto per scorrere la pagina;
  // `pointerleave` è il mouse che esce prima di rilasciare. In entrambi i casi il
  // gesto non è più un tocco su questo cursore.
  const abort = () => {
    press.current = null;
  };

  return (
    <div
      className={`relative flex h-11 touch-manipulation items-center ${disabled ? "" : "cursor-pointer"}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={abort}
      onPointerLeave={abort}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 h-2 rounded-full"
        style={{ backgroundImage: ZONES }}
      />
      <input
        ref={input}
        type="range"
        min={0}
        max={100}
        step={STEP}
        value={position}
        disabled={disabled}
        aria-label={`Quanto ne resta di ${label}`}
        // da qui arrivano solo la tastiera e le tecnologie assistive: il puntatore
        // non raggiunge più l'input
        onChange={(event) => setPosition(Number(event.target.value))}
        onKeyUp={() => commit(position)}
        onBlur={() => commit(position)}
        className="pointer-events-none relative h-11 w-full appearance-none bg-transparent disabled:opacity-50"
      />
    </div>
  );
}
