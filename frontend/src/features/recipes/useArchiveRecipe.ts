import { useMutation, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { setRecipeArchived, type RecipePage } from "./api";
import { useNotice } from "../../components/ui/noticeContext";

type ArchivedRecipe = { id: string; title: string };

/** Le pagine del ricettario in cache senza una ricetta, col totale che la conta una volta
 * in meno. Tornano le stesse pagine, intatte, se la ricetta non c'era: niente
 * aggiornamento inutile per React. Uno spread della pagina, non una ricostruzione: una
 * pagina porta anche `totalIsLowerBound` (R-D), e ricostruirla a mano perderebbe quel
 * campo. */
export function withoutRecipe(
  data: InfiniteData<RecipePage> | undefined,
  id: string
): InfiniteData<RecipePage> | undefined {
  if (!data || !data.pages.some((page) => page.recipes.some((recipe) => recipe.id === id))) {
    return data;
  }
  return {
    ...data,
    pages: data.pages.map((page) => ({
      ...page,
      recipes: page.recipes.filter((recipe) => recipe.id !== id),
      total: page.total === null ? null : Math.max(page.total - 1, 0),
    })),
  };
}

/** Eliminare una ricetta, dal dettaglio (T3 Consegna 4; spec §3.5, l'avviso che assorbe la
 * lapide del ricettario). Archivia, toglie la riga dal ricettario in cache, alza l'avviso
 * «Eliminata: <titolo>» con «Annulla», e porta al ricettario.
 *
 * Un gancio e non un pezzo del dettaglio perché il dettaglio si ridisegna (Consegna 5) e
 * deve continuare a eliminare nello stesso modo. Il doppio tocco lo ferma `busy` sul
 * pulsante che chiama `archive`: `pending` serve a quello. */
export function useArchiveRecipe(): {
  archive(recipe: { id: string; title: string }): void;
  pending: boolean;
} {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const notice = useNotice();

  // Eliminare e ripristinare cambiano cosa elencano il ricettario e il filtro per
  // categoria, oltre al dettaglio stesso: si rinfrescano tutti e tre.
  function refresh(id: string) {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["recipes"] }),
      queryClient.invalidateQueries({ queryKey: ["recipe-categories"] }),
      queryClient.invalidateQueries({ queryKey: ["recipe", id] }),
    ]);
  }

  // L'annulla vive nell'avviso, che è dell'app e non di chi ha eliminato: si tocca anche
  // quando il dettaglio non c'è più. Per questo non è una useMutation (legata al
  // componente) ma una chiamata col queryClient dell'app, come in Dispensa. Se fallisce,
  // un avviso nuovo lo dice e offre di riprovare: la ricetta è eliminata davvero, e
  // perdere l'annulla qui sarebbe il vicolo cieco.
  function restore(recipe: ArchivedRecipe): void {
    setRecipeArchived(recipe.id, false).then(
      () => refresh(recipe.id),
      () =>
        notice({
          text: `Non sono riuscito a riportare «${recipe.title}» nel ricettario.`,
          action: { label: "Riprova", onClick: () => restore(recipe) },
        })
    );
  }

  const mutation = useMutation({
    mutationFn: (recipe: ArchivedRecipe) => setRecipeArchived(recipe.id, true),
    onSuccess: (_archived, recipe) => {
      // prima di tornare al ricettario: una pagina in cache che la contiene ancora la
      // mostrerebbe per il tempo della rilettura, sotto l'avviso che la dice eliminata
      queryClient.setQueriesData<InfiniteData<RecipePage>>({ queryKey: ["recipes"] }, (data) =>
        withoutRecipe(data, recipe.id)
      );
      notice({
        text: `Eliminata: ${recipe.title}`,
        action: { label: "Annulla", onClick: () => restore(recipe) },
      });
      // `replace`: la ricetta eliminata lascia il posto al ricettario, e «indietro» non
      // ci riporta sopra
      navigate("/ricette", { replace: true });
      void refresh(recipe.id);
    },
    // la ricetta resta dov'è, e con lei il gesto: l'avviso offre di riprovare
    onError: (_error, recipe) =>
      notice({
        text: "Non sono riuscito a eliminarla: è ancora nel ricettario.",
        action: { label: "Riprova", onClick: () => archive(recipe) },
      }),
  });

  // Una dichiarazione col suo tipo, e non `mutation.mutate` scritto dentro le opzioni:
  // il «Riprova» qui sopra richiama la mutazione da dentro il suo stesso inizializzatore,
  // e senza un tipo dichiarato TypeScript non saprebbe dedurre quello di `mutation`
  // (TS7022). `mutate` è stabile: vale anche chiamata da un avviso di un render prima.
  function archive(recipe: ArchivedRecipe): void {
    mutation.mutate(recipe);
  }

  return { archive, pending: mutation.isPending };
}
