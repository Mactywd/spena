import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { createRecipe, draftRecipe } from "../recipes/api";
import { BackLink } from "../../components/BackLink";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { RecipeForm } from "../recipe-form/RecipeForm";
import { EMPTY_FORM, applyDraft, type RecipeFormValues } from "../recipe-form/formModel";
import { useNotice } from "../../components/ui/noticeContext";
import type { RecipeDraft } from "../../domain/types";

const SOURCE_REF_MAX = 500;

/** `source_ref` sta in 500 caratteri, il prompt può arrivarne a 1000: la
 * provenienza si accorcia, il testo scritto no — quello resta nel suo campo.
 * Senza questo, un prompt lungo faceva rifiutare il salvataggio con un 422. */
function sourceRef(prompt: string): string {
  const ref = `prompt: ${prompt}`;
  return ref.length <= SOURCE_REF_MAX ? ref : `${ref.slice(0, SOURCE_REF_MAX - 1)}…`;
}

// Lo schermo che tiene insieme la dipendenza meno affidabile dell'app e la via
// d'uscita da tutti i suoi guasti. L'AI può non rispondere, rispondere con qualcosa di
// inutilizzabile, o proporre un ingrediente che in anagrafica non esiste: nessuno di
// questi casi può diventare una pagina d'errore.
//
// Per questo il modulo della ricetta è SEMPRE in pagina, non dietro un `draft` né
// dietro un `propose.isError`. Tre ragioni, in ordine di peso:
//  1. `createRecipe` ha qui l'unico punto di chiamata del frontend: se il modulo vive
//     dentro una condizione, scrivere una ricetta a mano è una cosa che l'app non sa
//     fare finché quella condizione non è vera.
//  2. Una via d'uscita che si apre solo dopo un guasto si rompe insieme al guasto:
//     basta sbagliare la condizione e il vicolo cieco torna. Un modulo senza condizioni
//     non ha nessun flag da sbagliare.
//  3. Chiedere all'AI diventa un aiuto sul modulo — precompila i campi — invece di
//     essere il cancello da cui passare per averlo.
//
// Il modulo è `RecipeForm` (R10), lo stesso della modifica: qui sopra resta la
// richiesta all'AI, e la bozza lo riempie con `applyDraft`.
export function AiDraftScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const notice = useNotice();

  const [prompt, setPrompt] = useState("");
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const [values, setValues] = useState<RecipeFormValues>(EMPTY_FORM);

  const propose = useMutation({
    mutationFn: () => draftRecipe(prompt),
    onSuccess: (result) => {
      setDraft(result);
      setValues((prev) => applyDraft(prev, result));
    },
  });

  return (
    <div className="flex flex-col gap-4 px-4 pt-2 pb-4">
      <BackLink to="/ricette" label="Ricette" />
      <h1 className="text-2xl font-semibold tracking-tight">Scrivi una ricetta</h1>

      <div className="flex flex-col gap-2">
        <label htmlFor="prompt" className="text-sm text-ink-soft">Cosa vuoi cucinare</label>
        <textarea
          id="prompt"
          aria-label="Cosa vuoi cucinare"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder="Qualcosa di veloce con quello che ho"
        />
        <button
          type="button"
          onClick={() => propose.mutate()}
          disabled={prompt.trim().length < 3 || propose.isPending}
          className={buttonClasses("primary", "block")}
        >
          {propose.isPending ? "Propongo…" : "Proponi"}
        </button>
        <p className="text-xs text-ink-soft">
          Chiedere all'AI è facoltativo: precompila il modulo qui sotto, che funziona anche da
          solo.
        </p>

        {/* il testo scritto resta qui sopra qualunque sia l'esito, e il modulo
            qui sotto c'era già prima: il guasto non toglie niente */}
        {propose.isError && (
          <p role="alert" className="text-sm text-low">
            La stesura AI non è disponibile. Il modulo qui sotto resta tuo: scrivi la ricetta a
            mano e salvala.
          </p>
        )}
      </div>

      <div className="border-t border-line pt-4">
        <RecipeForm
          values={values}
          onChange={setValues}
          save={(body) =>
            createRecipe({
              ...body,
              // la provenienza dice il vero: senza bozza questa ricetta l'ha scritta
              // una persona, e spacciarla per "ai" sarebbe una bugia nello storico
              source: draft ? "ai" : "manual",
              source_ref: draft ? sourceRef(prompt) : null,
            })
          }
          onSaved={(recipe) => {
            // la ricetta appena scritta deve apparire nel ricettario al prossimo giro
            void queryClient.invalidateQueries({ queryKey: ["recipes"] });
            // «Salvata.» dall'avviso unico (T4), prima di lasciare il modulo:
            // `NoticeProvider` sta sopra il router, e l'avviso resta passando al dettaglio
            notice({ text: "Salvata." });
            navigate(`/ricette/${recipe.id}`);
          }}
          submitLabel="Salva nel ricettario"
        />
      </div>
    </div>
  );
}
