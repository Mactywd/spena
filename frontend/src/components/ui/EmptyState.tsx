import type { ReactNode } from "react";

/** Una schermata vuota che invita invece di scusarsi: cosa manca, perché, e cosa fare. */
export function EmptyState({ title, body, action }: { title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-2xl bg-card p-4">
      <h2 className="text-base font-semibold">{title}</h2>
      {body && <p className="text-sm text-ink-soft">{body}</p>}
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}
