import type { MouseEvent, ReactNode } from "react";
import { buttonClasses, type ButtonShape, type ButtonVariant } from "./buttonClasses";
import type { IconComponent } from "./icons";

type Common = {
  variant?: ButtonVariant;
  shape?: ButtonShape;
  type?: "button" | "submit";
  onClick?: () => void;
  /** Un'azione che adesso non si può fare (un modulo incompleto). Il browser toglie il
   * fuoco a un pulsante che diventa `disabled`: per «sto già lavorando» c'è `busy`. */
  disabled?: boolean;
  /** Una richiesta partita da qui è in volo (T3 Consegna 2). Il pulsante si spegne con
   * `aria-disabled` e non con `disabled`, così tiene il fuoco: dopo una ✕ fallita chi
   * naviga da tastiera lo ritrovava sul `body`. Il tocco si ignora qui dentro, e non in
   * ogni chiamante, perché nessuno possa dimenticare la guardia — come fanno a mano le
   * tacche (`StockGauge`) e la casella della lista. */
  busy?: boolean;
  className?: string;
  "aria-describedby"?: string;
};

// Le due forme della regola delle icone (spec T3 §2), e nessuna terza: un pulsante di
// sola icona senza `label` non compila, perché un pulsante muto per uno screen reader
// è un pulsante che non c'è.
type WithText = Common & { children: ReactNode; icon?: IconComponent; label?: never };
type IconOnly = Common & { icon: IconComponent; label: string; children?: never };

export function Button(props: WithText | IconOnly) {
  const {
    variant = "secondary",
    type = "button",
    onClick,
    disabled,
    busy = false,
    className = "",
  } = props;
  const Icon = props.icon;
  const iconOnly = props.label !== undefined;
  const shape = props.shape ?? (iconOnly ? "icon" : "pill");

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    if (busy) {
      // anche l'invio del modulo: un submit in volo non deve partire una seconda volta
      event.preventDefault();
      return;
    }
    onClick?.();
  }

  return (
    <button
      type={type}
      onClick={handleClick}
      disabled={disabled}
      aria-disabled={busy || undefined}
      aria-label={iconOnly ? props.label : undefined}
      aria-describedby={props["aria-describedby"]}
      className={`${buttonClasses(variant, shape)} ${className}`}
    >
      {Icon && <Icon aria-hidden="true" className={iconOnly ? "size-5" : "size-[1.1em]"} stroke={1.8} />}
      {props.children}
    </button>
  );
}
