import { useId, type MouseEvent, type ReactNode } from "react";
import { buttonClasses, type ButtonShape, type ButtonVariant } from "./buttonClasses";
import type { IconComponent } from "./icons";

// La regola dei pulsanti spenti, una per tutta l'app (T3 Consegna 6a, decisa da Mattia):
// - una richiesta partita da qui è in volo → `busy`;
// - l'azione non si può ancora fare, e chi guarda può rimediare → `unavailableReason`,
//   col perché scritto sotto;
// - `disabled` nativo solo dove nessuna delle due vale.
// `busy` e `unavailableReason` spengono con `aria-disabled` e non con `disabled`: il
// browser toglie il fuoco a un pulsante che diventa `disabled`, e chi usa la tastiera lo
// ritrova sul `body`; e un `disabled` non si raggiunge nemmeno col Tab, quindi il suo
// perché non lo sente nessuno.
type Common = {
  variant?: ButtonVariant;
  shape?: ButtonShape;
  type?: "button" | "submit";
  onClick?: () => void;
  /** Un'azione che adesso non si può fare, dove non c'è niente da aspettare né da
   * spiegare. Il browser toglie il fuoco a un pulsante che diventa `disabled`: per «sto
   * già lavorando» c'è `busy`, per «non ancora» c'è `unavailableReason`. */
  disabled?: boolean;
  /** Una richiesta partita da qui è in volo (T3 Consegna 2). Il pulsante si spegne con
   * `aria-disabled` e non con `disabled`, così tiene il fuoco: dopo una ✕ fallita chi
   * naviga da tastiera lo ritrovava sul `body`. Il tocco si ignora qui dentro, e non in
   * ogni chiamante, perché nessuno possa dimenticare la guardia — come fanno a mano le
   * tacche (`StockGauge`) e la casella della lista.
   *
   * Il clic risale comunque ai gestori `onClick` degli antenati: si ignora solo qui
   * dentro, mentre un pulsante `disabled` non ne manda nessuno. Nessun chiamante di oggi
   * sta dentro un elemento cliccabile; chi ce lo mette lo guardi. */
  busy?: boolean;
  /** «Non si può ancora», col perché (T3 Consegna 6a): il nome vuoto, niente di scelto.
   * Spento con `aria-disabled` come `busy`: tocco e invio del modulo si ignorano qui
   * dentro — anche l'Invio in un campo, che il browser fa arrivare al submit come un
   * clic su questo pulsante — e il fuoco resta. Il perché lo scrive `Button` sotto di sé,
   * in un `<p>` piccolo, e lo collega con `aria-describedby` dopo quello del chiamante:
   * chi ascolta lo sente arrivando sul pulsante, chi guarda lo legge sotto.
   *
   * Il `<p>` è un fratello del `<button>`, non un figlio: il chiamante mette il pulsante
   * dove una riga sotto di lui ci sta (una colonna, un blocco), e mai dentro un `<p>`.
   * Una stringa vuota non è un motivo. Come per `busy`, il clic risale comunque agli
   * antenati. */
  unavailableReason?: string;
  className?: string;
  "aria-describedby"?: string;
  /** Per chi apre e chiude qualcosa sotto di sé («Spostalo», «Sposta»). */
  "aria-expanded"?: boolean;
  /** Il pannello che questo pulsante apre e chiude (i «Filtri» del ricettario, T3
   * Consegna 4), accanto ad `aria-expanded`. Passa così com'è. */
  "aria-controls"?: string;
  /** Per un interruttore («Mostra password»). */
  "aria-pressed"?: boolean;
};

// Le due forme della regola delle icone (spec T3 §2), e nessuna terza: un pulsante di
// sola icona senza `label` non compila, perché un pulsante muto per uno screen reader
// è un pulsante che non c'è.
type WithText = Common & {
  children: ReactNode;
  icon?: IconComponent;
  label?: never;
  /** Il nome per chi ascolta, quando deve dire più del testo in vista: «Abbina» si
   * sente «Abbina: cosa strana» (T3 Consegna 6a). Il testo in vista sta all'inizio del
   * nome (WCAG 2.5.3, «label in name»): chi comanda a voce dice quel che vede. Prima lo
   * si otteneva con uno `sr-only` dentro al pulsante — che Chromium staccava con uno
   * spazio — o riscrivendo a mano il markup di questo componente. */
  accessibleName?: string;
};
type IconOnly = Common & {
  icon: IconComponent;
  label: string;
  children?: never;
  accessibleName?: never;
};

export function Button(props: WithText | IconOnly) {
  const {
    variant = "secondary",
    type = "button",
    onClick,
    disabled,
    busy = false,
    unavailableReason,
    className = "",
  } = props;
  const reasonId = useId();
  const Icon = props.icon;
  const iconOnly = props.label !== undefined;
  const shape = props.shape ?? (iconOnly ? "icon" : "pill");
  // una stringa vuota non è un motivo: i chiamanti scrivono `cond ? "…" : undefined`
  const reason = unavailableReason ? unavailableReason : null;
  const inert = busy || reason !== null;
  const describedBy =
    [props["aria-describedby"], reason !== null ? reasonId : undefined].filter(Boolean).join(" ") ||
    undefined;

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    if (inert) {
      // anche l'invio del modulo: un submit in volo non deve partire una seconda volta,
      // e uno «non ancora» non deve partire affatto
      event.preventDefault();
      return;
    }
    onClick?.();
  }

  // Un frammento, sempre: il `<button>` resta il primo figlio con o senza motivo, e
  // React non lo fa rinascere quando il motivo compare o sparisce — rinato, perderebbe
  // il fuoco proprio come con `disabled`
  return (
    <>
      <button
        type={type}
        onClick={handleClick}
        disabled={disabled}
        aria-disabled={inert || undefined}
        aria-label={iconOnly ? props.label : props.accessibleName}
        aria-describedby={describedBy}
        aria-expanded={props["aria-expanded"]}
        aria-controls={props["aria-controls"]}
        aria-pressed={props["aria-pressed"]}
        className={`${buttonClasses(variant, shape)} ${className}`}
      >
        {Icon && <Icon aria-hidden="true" className={iconOnly ? "size-5" : "size-[1.1em]"} stroke={1.8} />}
        {props.children}
      </button>
      {reason !== null && (
        <p id={reasonId} className="pt-1 text-xs text-ink-faint">
          {reason}
        </p>
      )}
    </>
  );
}
