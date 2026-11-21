import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Checkbox } from "../../components/ui/Checkbox";
import { Chip } from "../../components/ui/Chip";
import { useNotice } from "../../components/ui/noticeContext";
import type { ChangeCard as ChangeCardData, ChangeRow, PantryStatus } from "../../domain/types";
import { SLOT_LABELS, longDayLabel } from "../meals/format";
import { fetchPantry } from "../pantry/api";
import { STATUS_LABELS } from "../pantry/statusLabels";
import {
  addCardRow,
  applyCard,
  cardKey,
  discardCard,
  invalidateAfterCard,
} from "./api";

// Voce | Ora | Diventa: la casella e la voce stanno nelle prime due colonne (la label le
// prende insieme), così a 375 px la voce si spezza invece di spingere la pagina di lato
const GRID = "grid grid-cols-[2.75rem_minmax(0,1fr)_4.5rem_8rem] items-center gap-x-2";
const STATUSES: PantryStatus[] = ["available", "low", "finished"];

function nowText(row: ChangeRow): string {
  if (row.kind === "pantry") return row.from_status ? STATUS_LABELS[row.from_status] : "—";
  if (row.kind === "unlist") return "in lista";
  return row.listed ? "già in lista" : "—";
}

function becomesText(row: ChangeRow): string {
  if (row.kind === "pantry") return row.to_status ? STATUS_LABELS[row.to_status] : "—";
  return row.kind === "unlist" ? "via dalla lista" : "in lista";
}

type Edits = Record<string, { checked?: boolean; to?: PantryStatus }>;

/** La scheda dei cambi (spec §6.2): voce, ora, diventa. Caselle e stati si correggono
 * solo qui, in locale; partono con «Applica». Nessuna regola: tutto viene dal server. */
export function ChangeCard({ card }: { card: ChangeCardData }) {
  const queryClient = useQueryClient();
  const notice = useNotice();
  const [edits, setEdits] = useState<Edits>({});
  // la scheda che il server ha appena restituito, valida finché la prop non cambia
  const [fresh, setFresh] = useState<{ base: ChangeCardData; next: ChangeCardData } | null>(null);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [rawText, setRawText] = useState("");

  const shown = fresh && fresh.base === card ? fresh.next : card;
  const proposed = shown.status === "proposed";

  const pantry = useQuery({ queryKey: ["pantry"], queryFn: fetchPantry, enabled: proposed });

  function take(next: ChangeCardData) {
    setFresh({ base: card, next });
    queryClient.setQueryData(cardKey(next.id), next);
  }

  async function run(action: () => Promise<ChangeCardData>, done?: string) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      take(await action());
      if (done) notice({ text: done });
      invalidateAfterCard(queryClient);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const body = e.body as { code?: string; detail?: string; card?: ChangeCardData | null } | null;
        if (body?.card) take(body.card);
        if (body?.code === "card_applied") {
          notice({ text: "La scheda era già applicata." });
          invalidateAfterCard(queryClient);
        } else {
          setError(body?.detail ?? "Non si può fare.");
        }
      } else {
        setError("Non è andata a buon fine. Riprova.");
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  const rowChecked = (r: ChangeRow) => edits[r.id]?.checked ?? r.checked;
  const rowTo = (r: ChangeRow) => edits[r.id]?.to ?? r.to_status;
  const edit = (id: string, patch: Edits[string]) =>
    setEdits((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));

  function apply() {
    void run(
      () =>
        applyCard(
          shown.id,
          shown.rows
            .filter((r) => r.editable)
            .map((r) => {
              const to = rowTo(r);
              return {
                id: r.id,
                checked: rowChecked(r),
                ...(r.kind === "pantry" && to ? { to_status: to } : {}),
              };
            })
        ),
      "Scheda applicata."
    );
  }

  const inCard = new Set(shown.rows.map((r) => r.label.toLowerCase()));
  const query = search.trim().toLowerCase();
  const matches =
    query === "" || !pantry.data
      ? []
      : pantry.data
          .filter(
            (p) =>
              p.ingredient_name.toLowerCase().includes(query) &&
              !inCard.has(p.ingredient_name.toLowerCase()) &&
              !(p.product_name && inCard.has(p.product_name.toLowerCase()))
          )
          .slice(0, 6);

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex flex-col gap-2">
        <h2 className="text-base font-semibold break-words">{shown.title}</h2>
        {shown.meals.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {shown.meals.map((m) => (
              <li key={m.id}>
                <Chip tone="bg-brand-tint text-ink">
                  {`${longDayLabel(m.day)} · ${SLOT_LABELS[m.slot]}`}
                </Chip>
              </li>
            ))}
          </ul>
        )}
      </div>

      {shown.status === "applied" && <p className="text-sm font-medium">Applicata.</p>}
      {shown.status === "discarded" && <p className="text-sm font-medium">Scartata.</p>}
      {shown.status === "superseded" && (
        <p className="text-sm font-medium">Sostituita da una scheda più nuova.</p>
      )}

      {shown.rows.length > 0 && (
        <div role="table" aria-label="Cambi" className="flex flex-col">
          <div role="row" className={`${GRID} pb-1 text-xs font-semibold text-ink-faint`}>
            <span role="columnheader" className="col-span-2">Voce</span>
            <span role="columnheader">Ora</span>
            <span role="columnheader">Diventa</span>
          </div>
          {shown.rows.map((r) => (
            <div key={r.id} role="row" className="border-t border-line py-1">
              <div className={GRID}>
                {proposed ? (
                  <label role="cell" className="col-span-2 flex min-h-11 min-w-0 items-center gap-1">
                    <Checkbox
                      aria-label={`Applica: ${r.label}`}
                      checked={rowChecked(r)}
                      // non modificabile: `aria-disabled` e non `disabled`, come la lista;
                      // il cambio si ignora e la casella resta com'è
                      aria-disabled={!r.editable || undefined}
                      onChange={() => {
                        if (r.editable) edit(r.id, { checked: !rowChecked(r) });
                      }}
                    />
                    <span className="min-w-0 break-words">{r.label}</span>
                  </label>
                ) : (
                  <span role="cell" className="col-span-2 min-w-0 break-words">{r.label}</span>
                )}
                <span role="cell" className="text-xs break-words text-ink-soft">{nowText(r)}</span>
                <span role="cell" className="min-w-0">
                  {proposed && r.kind === "pantry" && r.editable ? (
                    <select
                      aria-label={`Diventa: ${r.label}`}
                      className="min-h-11 px-2 py-2"
                      value={rowTo(r) ?? "finished"}
                      onChange={(e) => edit(r.id, { to: e.target.value as PantryStatus })}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {STATUS_LABELS[s]}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-xs break-words text-ink-soft">{becomesText(r)}</span>
                  )}
                </span>
              </div>
              {r.note && (
                <p className={`pb-1 text-xs text-ink-soft ${proposed ? "pl-[3.25rem]" : ""}`}>{r.note}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {proposed && shown.rows.length === 0 && (
        <p className="text-sm text-ink-soft">
          Nessuna voce: aggiungi quello che il pasto usa, o scarta la scheda.
        </p>
      )}

      {proposed && (
        <>
          <div className="flex flex-col gap-1">
            {!shown.list_only && (
              <>
                <label htmlFor={`pantry-search-${shown.id}`} className="text-sm font-medium">
                  Cerca in dispensa
                </label>
                <input
                  id={`pantry-search-${shown.id}`}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                {matches.length > 0 && (
                  <ul className="flex flex-col">
                    {matches.map((p) => (
                      <li key={p.id}>
                        <button
                          type="button"
                          className="min-h-11 w-full text-left text-sm"
                          onClick={() => {
                            setSearch("");
                            void run(() => addCardRow(shown.id, { pantry_item_id: p.id }));
                          }}
                        >
                          {p.ingredient_name}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
          <form
            className="flex flex-col gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              const text = rawText.trim();
              if (text === "") return;
              setRawText("");
              void run(() => addCardRow(shown.id, { raw_text: text }));
            }}
          >
            <label htmlFor={`list-add-${shown.id}`} className="text-sm font-medium">
              Aggiungi alla lista
            </label>
            <div className="flex items-center gap-2">
              <input
                id={`list-add-${shown.id}`}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
              />
              <Button type="submit" busy={busy}>
                Aggiungi
              </Button>
            </div>
          </form>
          {error && <Alert>{error}</Alert>}
          <div className="flex flex-col gap-2">
            <Button variant="primary" shape="block" busy={busy} onClick={apply}>
              Applica
            </Button>
            <Button
              variant="ghost"
              shape="block"
              busy={busy}
              onClick={() => void run(() => discardCard(shown.id), "Scheda scartata.")}
            >
              Scarta
            </Button>
          </div>
        </>
      )}
      {!proposed && error && <Alert>{error}</Alert>}
    </Card>
  );
}
