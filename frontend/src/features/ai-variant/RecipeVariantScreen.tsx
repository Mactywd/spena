import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { createRecipe } from "../recipes/api";
import { Screen } from "../../components/ui/Screen";
import { useNotice } from "../../components/ui/noticeContext";
import { RecipeForm } from "../recipe-form/RecipeForm";
import { EMPTY_FORM, applyDraft } from "../recipe-form/formModel";
import { sourceRef } from "../ai-draft/sourceRef";
import { readVariantState, type VariantState } from "./variantState";

function VariantForm({ recipeId, state }: { recipeId: string; state: VariantState }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const notice = useNotice();
  // Una volta sola, dalla proposta: la categoria parte da quella dell'originale (la
  // proposta non ne ha, e una variante della torta resta un dolce), il resto da
  // `applyDraft` come nella bozza AI.
  const [values, setValues] = useState(() =>
    applyDraft({ ...EMPTY_FORM, category: state.originCategory }, state.draft)
  );

  return (
    <Screen
      title="Nuova variante"
      subtitle={`Variante di «${state.originTitle}»`}
      back={{ to: `/ricette/${recipeId}`, label: "Ricetta" }}
    >
      <p className="pb-3 text-sm break-words text-ink-soft">
        {`Hai chiesto: «${state.prompt}». Correggi quel che serve: salvando nasce una ricetta nuova, e l'originale resta com'è.`}
      </p>
      <RecipeForm
        values={values}
        onChange={setValues}
        // la foto e i tempi non passano di qui: li copia il server dall'originale, che
        // `derived_from_id` gli indica (Mattia, 2026-10-13; il modulo non li ha, R10 §7)
        save={(body) =>
          createRecipe({
            ...body,
            source: "ai",
            source_ref: sourceRef(state.prompt),
            derived_from_id: recipeId,
          })
        }
        onSaved={(saved) => {
          void queryClient.invalidateQueries({ queryKey: ["recipes"] });
          // «Salvata.» dall'avviso unico, prima di lasciare il modulo: `NoticeProvider`
          // sta sopra il router, e l'avviso resta passando al dettaglio
          notice({ text: "Salvata." });
          // `replace`: il dettaglio della variante prende il posto del modulo, e indietro
          // si torna all'originale, non a un modulo già salvato
          navigate(`/ricette/${saved.id}`, { replace: true });
        }}
        submitLabel="Salva la variante"
      />
    </Screen>
  );
}

/** `/ricette/:id/variante`: il modulo di una variante (R8), compilato dalla proposta che il
 * pannello del dettaglio ha messo nella cronologia. Salvando nasce una ricetta nuova col
 * legame all'originale (`derived_from_id`); l'originale non si tocca. Senza proposta — un
 * indirizzo scritto a mano — si torna all'originale, dove c'è il tasto: mai un vicolo
 * cieco. */
export function RecipeVariantScreen() {
  const { id = "" } = useParams();
  const location = useLocation();
  const state = readVariantState(location.state);
  if (state === null) return <Navigate to={`/ricette/${id}`} replace />;
  return <VariantForm recipeId={id} state={state} />;
}
