import type { ReactNode } from "react";

// Ogni rifiuto dell'app passa da qui. `role="alert"` non è decorazione: è ciò che fa
// leggere il messaggio a uno screen reader nel momento in cui appare, invece di
// lasciarlo come testo che comparirà sotto le dita di chi scorre.
//
// Il tono è una scelta. `error` dice «è andato male qualcosa», in rosso: il rosso vuol
// dire «manca» o «non è andata», e basta (spec T3 §3.1). `note` dice «non ho potuto»,
// in grigio, per una cosa che si fa comunque. `degraded` è il guasto di un aiuto — l'AI,
// oggi — con la strada a mano che resta: l'ambra di «funziona, ma non del tutto», la
// stessa di «quasi finito» e della ricerca che non risponde. Il guasto dell'AI ha un
// colore solo in tutta l'app (spec T3 §4.7), ed è questo.
const COLOUR = {
  error: "text-danger",
  note: "text-ink-soft",
  degraded: "text-low",
} as const;

export function Alert({
  children,
  className = "",
  tone = "error",
}: {
  children: ReactNode;
  className?: string;
  tone?: keyof typeof COLOUR;
}) {
  return (
    <p role="alert" className={`text-sm ${COLOUR[tone]} ${className}`}>
      {children}
    </p>
  );
}
