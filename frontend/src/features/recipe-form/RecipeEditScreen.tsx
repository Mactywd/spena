import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fetchRecipe, updateRecipe } from "../recipes/api";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { RecipeForm } from "./RecipeForm";
import { valuesFromRecipe } from "./formModel";
import type { RecipeDetail } from "../../domain/types";

const TITLE = "Modifica la ricetta";

function EditForm({ recipe }: { recipe: RecipeDetail }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Una volta sola, dalla ricetta caricata: una rilettura in background mentre si
  // scrive (il fuoco che torna alla finestra) non deve cancellare il lavoro.
  const [values, setValues] = useState(() => valuesFromRecipe(recipe));

  return (
    <>
      {recipe.owned_by_import && (
        <p className="pb-3 text-sm text-ink-soft">
          È una ricetta importata: salvando diventa tua, e l'import non la riscriverà più.
        </p>
      )}
      <RecipeForm
        values={values}
        onChange={setValues}
        save={(body) => updateRecipe(recipe.id, body)}
        onSaved={() => {
          void queryClient.invalidateQueries({ queryKey: ["recipe", recipe.id] });
          void queryClient.invalidateQueries({ queryKey: ["recipes"] });
          void queryClient.invalidateQueries({ queryKey: ["recipe-categories"] });
          navigate(`/ricette/${recipe.id}`, { state: { saved: true } });
        }}
        submitLabel="Salva le modifiche"
      />
    </>
  );
}

/** `/ricette/:id/modifica`: `RecipeForm` riempito dalla ricetta, salvato con la PUT
 * (R10 §6.2). La chiave della query è quella del dettaglio a 1×, quindi arrivando da lì
 * la ricetta è già in cache. */
export function RecipeEditScreen() {
  const { id = "" } = useParams();
  const back = { to: `/ricette/${id}`, label: "Ricetta" };
  const { data: recipe, isLoading, isError, refetch } = useQuery({
    queryKey: ["recipe", id, null],
    queryFn: () => fetchRecipe(id),
  });

  if (isLoading) {
    return (
      <Screen title={TITLE} back={back}>
        <p className="text-ink-soft">Carico…</p>
      </Screen>
    );
  }

  if (isError || !recipe) {
    return (
      <Screen title={TITLE} back={back}>
        <Alert>Non sono riuscito a caricare questa ricetta.</Alert>
        <button
          type="button"
          onClick={() => void refetch()}
          className={`${buttonClasses("secondary")} mt-3`}
        >
          Riprova
        </button>
      </Screen>
    );
  }

  // una ricetta eliminata non si modifica (il backend risponderebbe 409): lo schermo
  // dice dove sta l'uscita invece di offrire un modulo che non può salvare
  if (recipe.archived_at !== null) {
    return (
      <Screen title={TITLE} back={back}>
        <p className="text-ink-soft">
          Questa ricetta è stata eliminata: ripristinala dalla sua pagina, poi modificala.
        </p>
        <Link to={`/ricette/${id}`} className={`${buttonClasses("secondary")} mt-3`}>
          Vai alla ricetta
        </Link>
      </Screen>
    );
  }

  return (
    <Screen title={TITLE} back={back}>
      <EditForm recipe={recipe} />
    </Screen>
  );
}
