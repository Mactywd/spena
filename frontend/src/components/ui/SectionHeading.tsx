import type { ReactNode } from "react";

// I reparti della lista, le categorie della dispensa. Piccolo e maiuscoletto perché
// non è contenuto ma orientamento: si salta con l'occhio mentre si cerca il pomodoro.
export function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="px-1 pt-4 pb-1.5 text-xs font-semibold tracking-wider text-ink-faint uppercase">
      {children}
    </h2>
  );
}
