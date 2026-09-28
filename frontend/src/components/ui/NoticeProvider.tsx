import { useCallback, useEffect, useState, type ReactNode } from "react";
import { NOTICE_MS, NoticeContext, type NoticeInput } from "./noticeContext";

/** L'avviso di conferma unico (spec T3 §3.5). Uno alla volta: il nuovo prende il posto
 * del vecchio, perché due avvisi impilati sopra la barra coprirebbero la lista.
 *
 * Il fondo è `ink` e il testo `page`: rovesciato rispetto alla pagina in entrambi i
 * temi, così si stacca da qualunque cosa ci sia sotto senza un'ombra. La barra che si
 * accorcia dice quanto dura (dal giro: «la lapide dura 6 secondi e non lo dice»). */
export function NoticeProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<(NoticeInput & { key: number }) | null>(null);

  const show = useCallback((notice: NoticeInput) => {
    setCurrent({ ...notice, key: Date.now() + Math.random() });
  }, []);

  useEffect(() => {
    if (!current) return;
    const timer = setTimeout(() => setCurrent(null), NOTICE_MS);
    return () => clearTimeout(timer);
  }, [current]);

  return (
    <NoticeContext.Provider value={show}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 z-20 mx-auto max-w-md px-3"
        style={{ bottom: "calc(3.5rem + var(--safe-bottom) + 0.5rem)" }}
      >
        {/* la regione `status` c'è sempre, anche vuota: uno screen reader annuncia
            ciò che cambia dentro una regione che conosceva già, non una che nasce */}
        <div role="status">
          {current && (
            <div
              key={current.key}
              className="pointer-events-auto overflow-hidden rounded-xl bg-ink text-page"
            >
              <div className="flex min-h-11 items-center gap-3 px-3 py-2 text-sm">
                <span className="flex-1">{current.text}</span>
                {current.action && (
                  <button
                    type="button"
                    onClick={() => {
                      // l'azione può mostrare un avviso nuovo prima di tornare (l'«Annulla»
                      // del doppione lo fa: «Era già in lista.» prende il posto di questo
                      // stesso avviso). Chiudere solo se è rimasto questo: un `setCurrent(null)`
                      // incondizionato, applicato dopo, cancellerebbe anche quello nuovo — React
                      // mette in coda entrambi gli aggiornamenti dello stesso gestore
                      const key = current.key;
                      current.action!.onClick();
                      setCurrent((prev) => (prev?.key === key ? null : prev));
                    }}
                    className="min-h-11 shrink-0 px-2 font-semibold text-brand-tint"
                  >
                    {current.action.label}
                  </button>
                )}
              </div>
              <div
                aria-hidden="true"
                className="notice-timer h-0.5 origin-left bg-brand-tint"
                style={{ animationDuration: `${NOTICE_MS}ms` }}
              />
            </div>
          )}
        </div>
      </div>
    </NoticeContext.Provider>
  );
}
