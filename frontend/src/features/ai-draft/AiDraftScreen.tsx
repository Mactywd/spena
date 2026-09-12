import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { createRecipe, draftRecipe } from "../recipes/api";
import type { DraftIngredient, RecipeDraft } from "../../domain/types";

/** Le righe senza aggancio non entrano mai nel salvataggio: non esiste un
 * ingrediente a cui legarle, e inventarne uno silenziosamente sarebbe la bugia
 * che la dispensa non può permettersi. */
function isSavable(line: DraftIngredient, excluded: Set<string>): boolean {
  return line.ingredient_id !== null && !excluded.has(line.raw_name);
}

function matchNote(line: DraftIngredient): string {
  if (line.ingredient_id === null) return `${line.raw_name} non in anagrafica, sarà escluso`;
  if (line.confident) return line.matched_name ?? line.raw_name;
  return `${line.matched_name}, da confermare`;
}

// Lo schermo che chiude il cerchio con la dipendenza meno affidabile dell'app:
// Claude può non rispondere, rispondere con qualcosa di inutilizzabile, o
// proporre un ingrediente che in anagrafica non esiste. Nessuno di questi casi
// può diventare una pagina d'errore: tutti degradano a "scrivi e correggi a
// mano", che è esattamente quello che questo schermo offre già di default.
export function AiDraftScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [prompt, setPrompt] = useState("");
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  // righe con aggancio che l'utente ha deciso di non portare in salvataggio:
  // l'unico modo per correggere un aggancio incerto senza un editor di anagrafica
  const [excluded, setExcluded] = useState<Set<string>>(new Set());

  const propose = useMutation({
    mutationFn: () => draftRecipe(prompt),
    onSuccess: (result) => {
      setDraft(result);
      setTitle(result.title);
      setInstructions(result.instructions);
      setExcluded(new Set());
    },
  });

  const save = useMutation({
    mutationFn: () => {
      const ingredients = (draft?.ingredients ?? []).filter((line) => isSavable(line, excluded));
      return createRecipe({
        title,
        description: draft?.description ?? null,
        instructions,
        servings: draft?.servings ?? null,
        source: "ai",
        source_ref: `prompt: ${prompt}`,
        ingredients: ingredients.map((line) => ({
          ingredient_id: line.ingredient_id,
          role: line.role,
          quantity_text: line.quantity_text,
        })),
      });
    },
    onSuccess: (recipe) => {
      // la ricetta appena scritta deve apparire nel ricettario al prossimo giro:
      // senza invalidare la lista, la ricerca continuerebbe a mostrare dati vecchi
      void queryClient.invalidateQueries({ queryKey: ["recipes"] });
      navigate(`/ricette/${recipe.id}`);
    },
  });

  function toggleExcluded(rawName: string) {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(rawName)) next.delete(rawName);
      else next.add(rawName);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold">Scrivi una ricetta con l'AI</h1>

      <label htmlFor="prompt" className="text-sm text-neutral-600">Cosa vuoi cucinare</label>
      <textarea
        id="prompt"
        aria-label="Cosa vuoi cucinare"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={3}
        placeholder="Qualcosa di veloce con quello che ho"
        className="rounded-lg border border-neutral-300 px-3 py-2"
      />
      <button
        type="button"
        onClick={() => propose.mutate()}
        disabled={prompt.trim().length < 3 || propose.isPending}
        className="min-h-11 rounded-lg bg-emerald-700 px-4 py-3 text-white disabled:opacity-40"
      >
        {propose.isPending ? "Propongo…" : "Proponi"}
      </button>

      {/* il testo scritto resta qui sopra qualunque sia l'esito: un guasto
          dell'AI non è un motivo per far riscrivere tutto da capo */}
      {propose.isError && (
        <p role="alert" className="text-sm text-amber-700">
          La stesura AI non è disponibile. Puoi scrivere la ricetta a mano, qui sotto.
        </p>
      )}

      {draft && (
        <div className="flex flex-col gap-3 border-t pt-4">
          <label className="text-sm">
            Titolo
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>

          {draft.servings !== null && (
            <p className="text-xs text-neutral-400">Per {draft.servings} persone</p>
          )}

          <div>
            <h2 className="text-xs uppercase tracking-wide text-neutral-400">Ingredienti</h2>
            <ul className="divide-y divide-neutral-100">
              {draft.ingredients.map((line) => (
                <li key={line.raw_name} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <label className="flex min-h-11 flex-1 items-center gap-3">
                    {line.ingredient_id !== null && (
                      <input
                        type="checkbox"
                        aria-label={`Includi ${line.raw_name}`}
                        checked={!excluded.has(line.raw_name)}
                        onChange={() => toggleExcluded(line.raw_name)}
                        className="size-5 shrink-0"
                      />
                    )}
                    <span>
                      {line.raw_name}
                      {line.quantity_text && (
                        <span className="ml-2 text-neutral-400">{line.quantity_text}</span>
                      )}
                    </span>
                  </label>
                  <span className="shrink-0 text-right text-xs">
                    {line.ingredient_id === null || !line.confident ? (
                      <em className="text-amber-700">{matchNote(line)}</em>
                    ) : (
                      <span className="text-emerald-700">{matchNote(line)}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <label className="text-sm">
            Procedimento
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={8}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>

          <button
            type="button"
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="min-h-11 rounded-lg bg-emerald-700 px-4 py-3 text-white disabled:opacity-40"
          >
            {save.isPending ? "Salvo…" : "Salva nel ricettario"}
          </button>

          {/* l'errore sta accanto al pulsante che ha fallito, non in testa allo
              schermo: titolo, procedimento e correzioni agli agganci restano
              tutti qui, pronti per un altro tentativo */}
          {save.isError && (
            <p role="alert" className="text-sm text-red-600">
              Non sono riuscito a salvare la ricetta. Riprova.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
