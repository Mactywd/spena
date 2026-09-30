import type { InputHTMLAttributes } from "react";

/** La casella di casa (spec T3 §4.7, dal giro: «le caselle sono da 20×20»). Il
 * quadratino si vede da 24 px, ma il bersaglio è il quadrato da 44×44 intorno a lui: la
 * regola dei 44 px vale per l'area di tocco, non per il disegno (spec §3.2).
 *
 * Va messa dentro una `<label>`: è la label che rende cliccabile il quadrato intero,
 * come per ogni casella nativa. Il colore della spunta è il verde dell'app. */
export function Checkbox(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "className">) {
  return (
    <span className="flex size-11 shrink-0 items-center justify-center">
      <input type="checkbox" {...props} className="size-6 accent-brand aria-disabled:opacity-40" />
    </span>
  );
}
