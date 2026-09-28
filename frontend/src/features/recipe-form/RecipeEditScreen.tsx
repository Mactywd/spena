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
        onSaved={(saved) => {
          // la risposta della PUT è la ricetta a 1×, la stessa della GET senza porzioni:
          // il dettaglio la mostra subito, e «Salvata» non sta mai sopra la versione di
          // prima mentre la rilettura è in viaggio. Le altre chiavi (le porzioni, il
          // ricettario, le categorie) si rileggono come prima.
          queryClient.setQueryData(["recipe", recipe.id, null], saved);
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
 * (R10 §6.2). La chiave della query è quella del dettaglio a 1×.
 *
 * Il modulo nasce solo da una risposta letta dopo l'apertura, mai dalla cache: la PUT
 * rimpiazza la ricetta intera, e un modulo costruito su una copia vecchia rimanderebbe
 * al server i valori vecchi. Succedeva davvero: dal dettaglio riporzionato la chiave
 * attiva è `["recipe", id, 3]`, e cambiare il costo lì rilegge solo quella — la copia a
 * 1× restava col costo di prima, e «Salva le modifiche» lo rimetteva zitto. Un giro in
 * più ad ogni apertura della modifica è il prezzo di non perdere niente. */
export function RecipeEditScreen() {
  const { id = "" } = useParams();
  const back = { to: `/ricette/${id}`, label: "Ricetta" };
  const { data: recipe, isError, isFetchedAfterMount, refetch } = useQuery({
    queryKey: ["recipe", id, null],
    queryFn: () => fetchRecipe(id),
    refetchOnMount: "always",
  });

  // anche con la ricetta in cache: finché la lettura fatta all'apertura non è tornata
  // (con la ricetta o con un errore), non c'è un modulo da costruire
  if (!isFetchedAfterMount) {
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
