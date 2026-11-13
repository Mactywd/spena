import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { BackLink } from "../../components/BackLink";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Chip } from "../../components/ui/Chip";
import { ErrorState } from "../../components/ui/ErrorState";
import { IconPencil, IconTrash } from "../../components/ui/icons";
import { IconToolbar } from "../../components/ui/IconToolbar";
import { useNotice } from "../../components/ui/noticeContext";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { Meal, MealBody, MealPatch } from "../../domain/types";
import { RecipeDetailView } from "../cooking/RecipeDetailScreen";
import { MEALS_KEY, deleteMeal, fetchMeal, updateMeal } from "./api";
import { MealForm } from "./MealForm";
import { SLOT_LABELS, longDayLabel, mealMarks } from "./format";

/** Solo i campi cambiati: `PATCH` usa quelli mandati (spec §5.2). */
function patchFrom(meal: Meal, body: MealBody): MealPatch {
  const patch: MealPatch = {};
  if (body.day !== meal.day) patch.day = body.day;
  if (body.slot !== meal.slot) patch.slot = body.slot;
  if (body.dish !== meal.dish) patch.dish = body.dish;
  if (body.sides !== meal.sides) patch.sides = body.sides;
  if (body.away !== meal.away) patch.away = body.away;
  if (Object.keys(patch).length > 0 && body.replace) patch.replace = true;
  return patch;
}

/** La schermata del piatto (spec 2026-11-12 §5.3). Qui si correggono, spostano ed
 * eliminano i pasti (decisione 12); la ricetta è del Task 8. */
export function MealScreen() {
  const { id = "" } = useParams();
  const meal = useQuery({ queryKey: [...MEALS_KEY, "meal", id], queryFn: () => fetchMeal(id) });
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const notice = useNotice();
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (meal.isError) {
    const gone = meal.error instanceof ApiError && meal.error.status === 404;
    return (
      <div className="px-4 pt-2">
        <BackLink to="/pasti" label="Pasti" />
        {gone ? (
          <p className="text-sm text-ink-soft">
            Questo pasto non c'è più. Torna alla settimana per vedere cosa c'è.
          </p>
        ) : (
          <ErrorState
            message="Il pasto non si carica."
            onRetry={() => meal.refetch()}
            retrying={meal.isFetching}
          />
        )}
      </div>
    );
  }
  if (!meal.data) {
    return <p className="px-4 pt-5 text-sm text-ink-soft">Carico il pasto…</p>;
  }
  const m = meal.data;
  const weekLink = `/pasti?settimana=${m.week}`;
  const marks = mealMarks(m);

  const refresh = () => queryClient.invalidateQueries({ queryKey: MEALS_KEY });

  async function makeOfficial() {
    setBusy(true);
    setError(null);
    try {
      await updateMeal(m.id, { status: "official" });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Non sono riuscito a farlo. Riprova fra poco.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await deleteMeal(m.id);
      void refresh();
      notice({ text: "Pasto eliminato." });
      navigate(weekLink);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Non sono riuscito a eliminarlo. Riprova fra poco."
      );
      setBusy(false);
    }
  }

  return (
    <div className="px-4 pb-4 pt-2">
      <BackLink to={weekLink} label="Pasti" />
      <p className="text-sm text-ink-soft">
        {longDayLabel(m.day)} · {SLOT_LABELS[m.slot]}
      </p>
      <div className="flex items-start justify-between gap-3 pb-1">
        <h1 className="min-w-0 text-2xl font-semibold tracking-tight break-words">{m.dish}</h1>
        <IconToolbar label="Azioni del pasto">
          <Button
            variant="ghost"
            icon={IconPencil}
            label="Correggi"
            onClick={() => {
              setEditing(true);
              setConfirming(false);
            }}
          />
          <Button
            variant="ghost"
            icon={IconTrash}
            label="Elimina"
            onClick={() => {
              setConfirming(true);
              setEditing(false);
            }}
          />
        </IconToolbar>
      </div>
      {m.sides && <p className="break-words text-sm text-ink-soft">{m.sides}</p>}
      {marks.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-2">
          {marks.map((mark) => (
            <Chip key={mark} tone="bg-low-tint text-ink">
              {mark}
            </Chip>
          ))}
        </div>
      )}

      {editing && (
        <div className="pt-4">
          <MealForm
            initial={{
              day: m.day,
              slot: m.slot,
              dish: m.dish,
              sides: m.sides,
              away: m.away,
              leftover_of_id: m.leftover_of?.id ?? null,
            }}
            slotEditable
            leftoverChoices={[]}
            submitLabel="Salva le modifiche"
            save={async (body) => {
              const patch = patchFrom(m, body);
              if (Object.keys(patch).length > 0) await updateMeal(m.id, patch);
            }}
            onSaved={() => {
              void refresh();
              setEditing(false);
            }}
            onCancel={() => setEditing(false)}
          />
        </div>
      )}

      {confirming && (
        <div className="flex flex-col gap-2 pt-4">
          <p className="text-sm font-medium">Eliminare «{m.dish}»?</p>
          {m.recipe && !m.recipe.in_book && (
            <p className="text-sm text-ink-soft">
              La sua ricetta non è nel ricettario: si elimina con il pasto.
            </p>
          )}
          <div className="flex gap-2">
            <Button variant="danger" busy={busy} onClick={() => void remove()}>
              Sì, elimina
            </Button>
            <Button onClick={() => setConfirming(false)}>Annulla</Button>
          </div>
        </div>
      )}
      {error && <Alert className="pt-3">{error}</Alert>}

      {/* qui il piano 4 aggancia la scheda dei cambi di un pasto */}
      {m.status === "draft" && (
        <div className="pt-4">
          <Button variant="secondary" busy={busy} onClick={() => void makeOfficial()}>
            Rendi ufficiale
          </Button>
        </div>
      )}

      <div className="pt-4">
        {m.away ? (
          <p className="text-sm text-ink-soft">Fuori casa: non c'è niente da cucinare.</p>
        ) : m.status === "draft" ? (
          <p className="text-sm text-ink-soft">
            È una bozza: la ricetta arriva quando diventa ufficiale.
          </p>
        ) : !m.recipe && !m.leftover_of ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-ink-soft">Questo pasto non ha ancora una ricetta.</p>
            <div className="flex flex-wrap gap-2">
              <Link to={`/pasti/${m.id}/ricetta/nuova`} className={buttonClasses("secondary")}>
                Scrivi la ricetta
              </Link>
              <Link to={`/pasti/${m.id}/ricetta/scegli`} className={buttonClasses("secondary")}>
                Scegli dal ricettario
              </Link>
            </div>
          </div>
        ) : null}
        {m.recipe && (
          <RecipeDetailView
            key={m.recipe.id}
            id={m.recipe.id}
            meal={{ mealId: m.id, readOnly: false }}
          />
        )}
        {m.leftover_of && (
          <div className="flex flex-col gap-3">
            <Link
              to={`/pasti/${m.leftover_of.id}`}
              className="text-sm font-medium text-brand break-words"
            >
              Avanzo di «{m.leftover_of.dish}», {longDayLabel(m.leftover_of.day)} ·{" "}
              {SLOT_LABELS[m.leftover_of.slot]}
            </Link>
            {m.leftover_of.recipe_id ? (
              <RecipeDetailView
                key={m.leftover_of.recipe_id}
                id={m.leftover_of.recipe_id}
                meal={{ mealId: m.id, readOnly: true }}
              />
            ) : (
              <p className="text-sm text-ink-soft">Il pasto da cui viene non ha una ricetta.</p>
            )}
          </div>
        )}
        {/* qui, sotto la ricetta, il piano 3 mette la chat del piatto */}
      </div>
    </div>
  );
}
