import type { ReactNode } from "react";

// Ogni rifiuto dell'app passa da qui. `role="alert"` non è decorazione: è ciò che fa
// leggere il messaggio a uno screen reader nel momento in cui appare, invece di
// lasciarlo come testo che comparirà sotto le dita di chi scorre.
//
// Il tono è una scelta: `warning` dice «non ho potuto», `error` dice «è andato male
// qualcosa». Sono lo stesso rosso, diverso peso, perché due rossi diversi per due
// gradi di gravità non si imparano mai.
export function Alert({
  children,
  className = "",
  tone = "error",
}: {
  children: ReactNode;
  className?: string;
  tone?: "error" | "note";
}) {
  const colour = tone === "error" ? "text-danger" : "text-ink-soft";
  return (
    <p role="alert" className={`text-sm ${colour} ${className}`}>
      {children}
    </p>
  );
}
