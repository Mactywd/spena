import type { ReactNode } from "react";
import { buttonClasses, type ButtonShape, type ButtonVariant } from "./buttonClasses";
import type { IconComponent } from "./icons";

type Common = {
  variant?: ButtonVariant;
  shape?: ButtonShape;
  type?: "button" | "submit";
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  "aria-describedby"?: string;
};

// Le due forme della regola delle icone (spec T3 §2), e nessuna terza: un pulsante di
// sola icona senza `label` non compila, perché un pulsante muto per uno screen reader
// è un pulsante che non c'è.
type WithText = Common & { children: ReactNode; icon?: IconComponent; label?: never };
type IconOnly = Common & { icon: IconComponent; label: string; children?: never };

export function Button(props: WithText | IconOnly) {
  const { variant = "secondary", type = "button", onClick, disabled, className = "" } = props;
  const Icon = props.icon;
  const iconOnly = props.label !== undefined;
  const shape = props.shape ?? (iconOnly ? "icon" : "pill");
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={iconOnly ? props.label : undefined}
      aria-describedby={props["aria-describedby"]}
      className={`${buttonClasses(variant, shape)} ${className}`}
    >
      {Icon && <Icon aria-hidden="true" className={iconOnly ? "size-5" : "size-[1.1em]"} stroke={1.8} />}
      {props.children}
    </button>
  );
}
