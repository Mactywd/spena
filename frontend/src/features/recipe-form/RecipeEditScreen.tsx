import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { fetchRecipe, isRecipeChanged, updateRecipe } from "../recipes/api";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { RecipeForm } from "./RecipeForm";
import { recipeBody, valuesFromRecipe } from "./formModel";
import { Button } from "../../components/ui/Button";
import { useNotice } from "../../components/ui/noticeContext";
import type { RecipeDetail } from "../../domain/types";

const TITLE = "Modifica la ricetta";

function EditForm({
  recipe,
  mealId,
  onReload,
}: {
  recipe: RecipeDetail;
  mealId: string | null;
  onReload: (fresh: RecipeDetail) => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const notice = useNotice();
  // Una volta sola, dalla ricetta caricata: una rilettura in background mentre si
  // scrive (il fuoco che torna alla finestra) non deve cancellare il lavoro.
  const [values, setValues] = useState(() => valuesFromRecipe(recipe));
  // la frase del server quando la ricetta è cambiata dopo che il modulo l'ha letta
  const [changed, setChanged] = useState<string | null>(null);
  const [overwriting, setOverwriting] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [reloadError, setReloadError] = useState(false);

  function saved(saved: RecipeDetail) {
    // la risposta della PUT è la ricetta a 1×, la stessa della GET senza porzioni:
    // il dettaglio la mostra subito, e «Salvata.» non sta mai sopra la versione di
    // prima mentre la rilettura è in viaggio. Le altre chiavi (le porzioni, il
    // ricettario, le categorie) si rileggono come prima.
    queryClient.setQueryData(["recipe", recipe.id, null], saved);
    void queryClient.invalidateQueries({ queryKey: ["recipe", recipe.id] });
    void queryClient.invalidateQueries({ queryKey: ["recipes"] });
    void queryClient.invalidateQueries({ queryKey: ["recipe-categories"] });
    // «Salvata.» dall'avviso unico (T4), non più da uno stato della cronologia che il
    // dettaglio doveva leggere e poi pulire
    notice({ text: "Salvata." });
    if (mealId) {
      // da un pasto si torna al pasto, che mostra la ricetta cambiata
      void queryClient.invalidateQueries({ queryKey: ["meals"] });
      navigate(`/pasti/${mealId}`, { replace: true });
      return;
    }
    // `replace`: il modulo lascia il posto al dettaglio, e «indietro» (quello di
    // Android per primo) non riapre un modulo già salvato
    navigate(`/ricette/${recipe.id}`, { replace: true });
  }

  async function overwrite() {
    setOverwriting(true);
    try {
      // senza versione: scrive comunque, come un client che non la manda
      saved(await updateRecipe(recipe.id, recipeBody(values)));
    } catch (err) {
      if (isRecipeChanged(err)) {
        setChanged(((err.body as { detail?: unknown }).detail as string) ?? changed);
      } else {
        setChanged(null);
        setReloadError(true);
      }
    } finally {
      setOverwriting(false);
    }
  }

  async function reload() {
    setReloading(true);
    setReloadError(false);
    try {
      onReload(await fetchRecipe(recipe.id));
    } catch {
      setReloadError(true);
    } finally {
      setReloading(false);
    }
  }

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
        save={async (body) => {
          setChanged(null);
          setReloadError(false);
          try {
            return await updateRecipe(recipe.id, body, recipe.version);
          } catch (err) {
            if (isRecipeChanged(err)) {
              const detail = (err.body as { detail?: unknown }).detail;
              setChanged(typeof detail === "string" ? detail : "La ricetta è cambiata mentre la correggevi.");
            }
            throw err;
          }
        }}
        onSaved={saved}
        submitLabel="Salva le modifiche"
      />
      {changed !== null && (
        <div className="space-y-3 pt-4">
          <Alert tone="note">{changed}</Alert>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" busy={overwriting} onClick={() => void overwrite()}>
              Salva comunque la mia
            </Button>
            <Button variant="secondary" busy={reloading} onClick={() => void reload()}>
              Ricarica la ricetta
            </Button>
          </div>
        </div>
      )}
      {reloadError && (
        <Alert>Non sono riuscito a completare l'operazione. Il modulo è com'era: riprova.</Alert>
      )}
    </>
  );
}

/** `/ricette/:id/modifica`: `RecipeForm` riempito dalla ricetta, salvato con la PUT
 * (R10 §6.2). La chiave della query è quella del dettaglio a 1×.
 *
 * Il modulo nasce solo da una risposta letta dopo l'apertura, mai dalla cache: la PUT
 * rimpiazza la ricetta intera, e un modulo costruito su una copia vecchia rimanderebbe
 * al server i valori vecchi. Succedeva davvero: dal dettaglio riporzionato la chiave
 * attiva è `["recipe", id, { servings: 3 }]`, e cambiare il costo lì rilegge solo quella — la copia a
 * 1× restava col costo di prima, e «Salva le modifiche» lo rimetteva zitto. Un giro in
 * più ad ogni apertura della modifica è il prezzo di non perdere niente. */
export function RecipeEditScreen() {
  const { id = "" } = useParams();
  // `?pasto=<id>`: la modifica è partita da un pasto, e a lui ritorna
  const mealId = useSearchParams()[0].get("pasto");
  const back = mealId
    ? { to: `/pasti/${mealId}`, label: "Pasto" }
    : { to: `/ricette/${id}`, label: "Ricetta" };
  const [fresh, setFresh] = useState<RecipeDetail | null>(null);
  const [reloads, setReloads] = useState(0);
  const { data: recipe, error, isError, isFetchedAfterMount, refetch } = useQuery({
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

  // una ricetta che non c'è più risponde 404: niente «Riprova», che non potrebbe
  // riuscire, e anche il ritorno in alto porta al ricettario — tornare alla ricetta
  // sparita sarebbe un giro a vuoto
  if (error instanceof ApiError && error.status === 404) {
    return (
      <Screen title={TITLE} back={{ to: "/ricette", label: "Ricette" }}>
        <Alert>Questa ricetta non c'è più.</Alert>
        <Link to="/ricette" className={`${buttonClasses("secondary")} mt-3`}>
          Torna al ricettario
        </Link>
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

  const current = fresh ?? recipe;
  return (
    <Screen title={TITLE} back={back}>
      {/* «Ricarica la ricetta» cambia la chiave: il modulo riparte da `valuesFromRecipe` */}
      <EditForm
        key={`${current.version}-${reloads}`}
        recipe={current}
        mealId={mealId}
        onReload={(next) => {
          setFresh(next);
          setReloads((n) => n + 1);
        }}
      />
    </Screen>
  );
}
