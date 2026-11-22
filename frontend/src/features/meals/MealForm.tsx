import { useState, type FormEvent } from "react";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";
import { ApiError } from "../../api/client";
import type { Meal, MealBody, MealSlot } from "../../domain/types";
import { SLOT_LABELS, longDayLabel } from "./format";

type Question =
  | { kind: "slot_taken"; message: string; body: MealBody; recipeGoes: boolean }
  | { kind: "leftover_after"; message: string; body: MealBody; leftovers: number }
  | { kind: "origin_out_of_reach"; message: string; body: MealBody };

/** Il pasto scritto a mano (spec 2026-11-12 §5.2). Il modulo non sa se crea o corregge:
 * `save` riceve il corpo intero e chi lo usa decide che cosa mandare. */
export function MealForm({
  initial,
  slotEditable,
  leftoverChoices,
  submitLabel,
  save,
  onSaved,
  onCancel,
}: {
  initial: MealBody;
  slotEditable: boolean;
  leftoverChoices: Meal[];
  submitLabel: string;
  save: (body: MealBody) => Promise<unknown>;
  onSaved: () => void;
  onCancel?: () => void;
}) {
  const [dish, setDish] = useState(initial.dish);
  const [sides, setSides] = useState(initial.sides ?? "");
  const [away, setAway] = useState(initial.away);
  const [day, setDay] = useState(initial.day);
  const [slot, setSlot] = useState<MealSlot>(initial.slot);
  const [leftover, setLeftover] = useState(initial.leftover_of_id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // l'occupante di un posto preso: il `detail` del server dice già «C'è già «X» …».
  // Con il corpo rifiutato: «Sostituisci» rimanda quello, non il modulo com'è ora (che
  // può già dire un altro posto, e cancellerebbe un pasto mai confermato). Se cambia
  // un campo qualunque (giorno, pasto, piatto, contorni, «Fuori casa», avanzo) la domanda
  // non vale più e sparisce, e tornano «Salva» e «Annulla» del modulo.
  // Tre domande, dal backend: il posto occupato (`slot_taken`, con l'occupante), l'avanzo
  // che verrebbe prima (`leftover_after`, con quanti sono) e l'avanzo spostato fuori dalla
  // finestra del suo pasto (`origin_out_of_reach`). Il frontend non decide quale.
  const [taken, setTaken] = useState<Question | null>(null);

  const body = (replace: boolean): MealBody => ({
    day,
    slot,
    dish: dish.trim(),
    sides: sides.trim() === "" ? null : sides.trim(),
    away,
    leftover_of_id: away || leftover === "" ? null : leftover,
    ...(replace ? { replace: true } : {}),
  });

  async function send(replace: boolean, sent?: MealBody) {
    setBusy(true);
    setError(null);
    setTaken(null);
    try {
      await save(sent ?? body(replace));
      onSaved();
    } catch (err) {
      const code =
        err instanceof ApiError && err.body && typeof err.body === "object"
          ? (err.body as { code?: unknown }).code
          : null;
      if (err instanceof ApiError && err.status === 409 && code === "slot_taken") {
        const occupant = (err.body as { occupant?: { recipe?: { in_book?: boolean } | null } | null })
          .occupant;
        setTaken({
          kind: "slot_taken",
          message: err.message,
          body: sent ?? body(replace),
          recipeGoes: Boolean(occupant?.recipe && occupant.recipe.in_book === false),
        });
      } else if (err instanceof ApiError && err.status === 409 && code === "leftover_after") {
        const count = (err.body as { leftovers?: unknown }).leftovers;
        setTaken({
          kind: "leftover_after",
          message: err.message,
          body: sent ?? body(replace),
          leftovers: typeof count === "number" ? count : 1,
        });
      } else if (err instanceof ApiError && err.status === 409 && code === "origin_out_of_reach") {
        setTaken({ kind: "origin_out_of_reach", message: err.message, body: sent ?? body(replace) });
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Non sono riuscito a salvare il pasto. Riprova fra poco.");
      }
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (dish.trim() === "") return;
    void send(false);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="meal-dish" className="text-sm font-medium">
          Piatto
        </label>
        <input
          id="meal-dish"
          value={dish}
          maxLength={200}
          onChange={(e) => {
            setDish(e.target.value);
            setTaken(null);
          }}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="meal-sides" className="text-sm font-medium">
          Accompagnamenti
        </label>
        <input
          id="meal-sides"
          value={sides}
          maxLength={200}
          placeholder="piadina · banana"
          onChange={(e) => {
            setSides(e.target.value);
            setTaken(null);
          }}
        />
      </div>
      {slotEditable && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor="meal-day" className="text-sm font-medium">
              Giorno
            </label>
            <input
              id="meal-day"
              type="date"
              value={day}
              onChange={(e) => {
                if (!e.target.value) return;
                setDay(e.target.value);
                setTaken(null);
              }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="meal-slot" className="text-sm font-medium">
              Pasto
            </label>
            <select
              id="meal-slot"
              value={slot}
              onChange={(e) => {
                setSlot(e.target.value as MealSlot);
                setTaken(null);
              }}
            >
              <option value="lunch">{SLOT_LABELS.lunch}</option>
              <option value="dinner">{SLOT_LABELS.dinner}</option>
            </select>
          </div>
        </div>
      )}
      <label className="flex min-h-11 items-center gap-1 text-sm">
        <Checkbox checked={away} onChange={() => {
            setAway(!away);
            setTaken(null);
          }}
        />
        Fuori casa
      </label>
      {leftoverChoices.length > 0 && !away && (
        <div className="flex flex-col gap-1">
          <label htmlFor="meal-leftover" className="text-sm font-medium">
            Avanzo di
          </label>
          <select
            id="meal-leftover"
            value={leftover}
            onChange={(e) => {
              setLeftover(e.target.value);
              setTaken(null);
            }}
          >
            <option value="">Nessuno</option>
            {leftoverChoices.map((m) => (
              <option key={m.id} value={m.id}>
                {`${m.dish} (${longDayLabel(m.day)}, ${SLOT_LABELS[m.slot].toLowerCase()})`}
              </option>
            ))}
          </select>
        </div>
      )}

      {taken && (
        <div className="flex flex-col gap-2">
          <Alert tone="note">{taken.message}</Alert>
          {taken.kind === "slot_taken" && taken.recipeGoes && (
            <p className="text-sm text-ink-soft">
              La sua ricetta non è nel ricettario: si elimina con il pasto.
            </p>
          )}
          <div className="flex gap-2">
            {taken.kind === "slot_taken" ? (
              <Button variant="danger" busy={busy} onClick={() => void send(true, { ...taken.body, replace: true })}>
                Sostituisci
              </Button>
            ) : taken.kind === "origin_out_of_reach" ? (
              <Button
                variant="danger"
                busy={busy}
                onClick={() => void send(true, { ...taken.body, detach_origin: true })}
              >
                Sposta e stacca dal pasto d'origine
              </Button>
            ) : (
              <Button
                variant="danger"
                busy={busy}
                onClick={() => void send(true, { ...taken.body, detach_leftovers: true })}
              >
                {taken.leftovers === 1 ? "Sposta e stacca l'avanzo" : "Sposta e stacca gli avanzi"}
              </Button>
            )}
            <Button onClick={() => setTaken(null)}>Annulla</Button>
          </div>
        </div>
      )}
      {error && <Alert>{error}</Alert>}

      {!taken && (
        <div className="flex gap-2">
          <Button
            type="submit"
            variant="primary"
            busy={busy}
            unavailableReason={dish.trim() === "" ? "Scrivi il piatto." : undefined}
          >
            {submitLabel}
          </Button>
          {onCancel && <Button onClick={onCancel}>Annulla</Button>}
        </div>
      )}
    </form>
  );
}
