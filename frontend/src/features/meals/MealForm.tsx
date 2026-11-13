import { useState, type FormEvent } from "react";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";
import { ApiError } from "../../api/client";
import type { Meal, MealBody, MealSlot } from "../../domain/types";
import { SLOT_LABELS, longDayLabel } from "./format";

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
  // l'occupante di un posto preso: il `detail` del server dice già «C'è già «X» …»
  const [taken, setTaken] = useState<string | null>(null);

  const body = (replace: boolean): MealBody => ({
    day,
    slot,
    dish: dish.trim(),
    sides: sides.trim() === "" ? null : sides.trim(),
    away,
    leftover_of_id: away || leftover === "" ? null : leftover,
    ...(replace ? { replace: true } : {}),
  });

  async function send(replace: boolean) {
    setBusy(true);
    setError(null);
    setTaken(null);
    try {
      await save(body(replace));
      onSaved();
    } catch (err) {
      const code =
        err instanceof ApiError && err.body && typeof err.body === "object"
          ? (err.body as { code?: unknown }).code
          : null;
      if (err instanceof ApiError && err.status === 409 && code === "slot_taken") {
        setTaken(err.message);
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
          onChange={(e) => setDish(e.target.value)}
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
          onChange={(e) => setSides(e.target.value)}
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
              onChange={(e) => e.target.value && setDay(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="meal-slot" className="text-sm font-medium">
              Pasto
            </label>
            <select
              id="meal-slot"
              value={slot}
              onChange={(e) => setSlot(e.target.value as MealSlot)}
            >
              <option value="lunch">{SLOT_LABELS.lunch}</option>
              <option value="dinner">{SLOT_LABELS.dinner}</option>
            </select>
          </div>
        </div>
      )}
      <label className="flex min-h-11 items-center gap-1 text-sm">
        <Checkbox checked={away} onChange={() => setAway(!away)} />
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
            onChange={(e) => setLeftover(e.target.value)}
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
          <Alert tone="note">{taken}</Alert>
          <div className="flex gap-2">
            <Button variant="danger" busy={busy} onClick={() => void send(true)}>
              Sostituisci
            </Button>
            <Button onClick={() => setTaken(null)}>Annulla</Button>
          </div>
        </div>
      )}
      {error && <Alert>{error}</Alert>}

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
    </form>
  );
}
