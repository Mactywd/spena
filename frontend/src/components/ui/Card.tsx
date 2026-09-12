import type { ReactNode } from "react";

// La superficie bianca su cui sta ogni cosa leggibile. Un solo raggio di curvatura
// (`rounded-card`) per tutta l'app: tre raggi diversi su tre schermate si notano
// anche senza saperli nominare, e fanno sembrare l'app montata a pezzi.
export function Card({
  children,
  className = "",
  pad = true,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  /** false per una lista: le righe portano il loro spazio, la scheda solo il bordo */
  pad?: boolean;
  /** `li` o `section` dove la semantica della lista conta */
  as?: "div" | "li" | "section" | "article";
}) {
  return <Tag className={`rounded-card bg-card ${pad ? "p-3" : ""} ${className}`}>{children}</Tag>;
}
