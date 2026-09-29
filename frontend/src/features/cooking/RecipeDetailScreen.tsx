import { useEffect, useRef, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { fetchRecipe, setRecipeArchived, updateRecipeCost } from "../recipes/api";
import { fetchPantry } from "../pantry/api";
import { ApiError } from "../../api/client";
import { CookSheet } from "./CookSheet";
import { ServingsStepper } from "./ServingsStepper";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { BackLink } from "../../components/BackLink";
import { RecipeImage } from "../recipes/RecipeImage";
import { CostPicker } from "../../components/ui/CostPicker";
import { revealAtTop } from "../../lib/revealAtTop";
import type { CookResult, RecipeIngredientLine } from "../../domain/types";

function statusNote(line: RecipeIngredientLine): string {
  if (line.availability === "missing") return "manca";
  if (line.availability === "available") return "disponibile";
  // l'unico caso interessante: quasi finito, dove il ruolo fa la differenza
  return line.satisfied ? "quasi finito, basta" : "quasi finito, non basta";
}

// Il numero viene dal backend, non da un conteggio fatto qui: quante voci sono
// tornate in lista lo sa solo chi ha applicato le transizioni (una lista può già
// contenere quell'ingrediente, e allora non si duplica).
function cookNote(result: CookResult): string {
  if (result.restocked === 0) return "Segnato. Niente è tornato in lista della spesa.";
  if (result.restocked === 1) return "Segnato. Una cosa è tornata in lista della spesa.";
  return `Segnato. ${result.restocked} cose sono tornate in lista della spesa.`;
}

export function RecipeDetailScreen() {
  const { id = "" } = useParams();
  const [cooking, setCooking] = useState(false);
  // l'esito dell'ultima cottura: il foglio si smonta subito dopo averla registrata,
  // e senza questo il gesto per cui esiste tutto il task non dice mai cosa ha fatto
  const [lastCook, setLastCook] = useState<CookResult | null>(null);

  // le porzioni chieste: è una vista, non si salva. Uscire dalla ricetta se ne
  // dimentica, ed è quel che vuole chi sta guardando cosa cucinare stasera.
  const [servings, setServings] = useState<number | null>(null);

  const queryClient = useQueryClient();
  const navigate = useNavigate();
  // «Salvata» arriva con la navigazione dalla modifica (R10 §6.2). Si legge una volta,
  // nello stato di questo schermo, e la voce della cronologia si pulisce subito (sotto),
  // come la lapide del ricettario: un «indietro» e un «avanti» non devono ridire
  // «Salvata» di un salvataggio vecchio.
  const location = useLocation();
  const savedNow = (location.state as { saved?: boolean } | null)?.saved === true;
  const [justSaved] = useState(savedNow);
  useEffect(() => {
    if (savedNow) navigate(location.pathname, { replace: true, state: null });
  }, [savedNow, navigate, location.pathname]);

  // Eliminare e ripristinare cambiano cosa elencano ricettario e filtro per categoria,
  // oltre al dettaglio stesso: si rinfrescano tutti e tre.
  const refreshAfterArchive = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["recipe", id] }),
      queryClient.invalidateQueries({ queryKey: ["recipes"] }),
      queryClient.invalidateQueries({ queryKey: ["recipe-categories"] }),
    ]);

  // «Elimina» archivia subito, senza chiedere: la conferma è la lapide con «Annulla»
  // nel ricettario, dove si torna (R10 §6.1). `replace`: la ricetta eliminata lascia il
  // posto al ricettario, e «indietro» non ci riporta sopra.
  const archive = useMutation({
    mutationFn: () => setRecipeArchived(id, true),
    onSuccess: (archived) => {
      void refreshAfterArchive();
      navigate("/ricette", {
        replace: true,
        state: { deletedRecipe: { id, title: archived.title } },
      });
    },
  });

  const restore = useMutation({
    mutationFn: () => setRecipeArchived(id, false),
    onSuccess: () => refreshAfterArchive(),
  });

  // Il valore mostrato è sempre quello che il server ha salvato, non quello toccato:
  // niente aggiornamento ottimistico, perché un tocco fallito che restasse a video
  // direbbe un costo che la ricetta non ha. La rilettura costa un giro, e il
  // selettore resta spento finché non è tornato.
  const setCost = useMutation({
    mutationFn: (cost: number | null) => updateRecipeCost(id, cost),
    onSuccess: async () => {
      await Promise.all([
        // il prefisso, non la chiave intera: le porzioni stanno in coda alla chiave
        queryClient.invalidateQueries({ queryKey: ["recipe", id] }),
        // la scheda del ricettario porta il costo anche lei
        queryClient.invalidateQueries({ queryKey: ["recipes"] }),
      ]);
    },
  });

  const {
    data: recipe,
    error: recipeError,
    isLoading: isRecipeLoading,
    isError: isRecipeError,
    refetch: refetchRecipe,
  } = useQuery({
    queryKey: ["recipe", id, servings],
    queryFn: () => fetchRecipe(id, servings ?? undefined),
    // le porzioni stanno nella chiave, quindi ogni tocco dello stepper è una chiave
    // nuova e senza cache: senza questo, `isLoading` torna vero e lo schermo intero
    // viene sostituito da «Carico…» a metà della rilettura — il pulsante sparisce da
    // sotto il dito e toccare «+» due volte di fila diventa impossibile. In locale
    // non si vede; in cucina, al telefono, è l'interazione principale.
    placeholderData: keepPreviousData,
  });

  // Serve solo per aprire il foglio di cottura: senza dispensa non si può dire
  // quali vasetti esistono, quindi un fallimento qui non può travestirsi da
  // "nessun vasetto da aggiornare" — altrimenti "Cucina" apparirebbe disponibile
  // ma produrrebbe un foglio vuoto, silenziosamente sbagliato.
  const {
    data: pantry,
    isLoading: isPantryLoading,
    isError: isPantryError,
    refetch: refetchPantry,
  } = useQuery({ queryKey: ["pantry"], queryFn: fetchPantry });

  // «Cucina» sta in fondo, sotto il procedimento, e il foglio prende il posto di
  // ingredienti e procedimento: la pagina si accorcia ma resta scorsa in fondo, e le
  // prime righe del foglio — con «Tocca solo ciò che è cambiato» — restano fuori
  // vista. Si porta in vista il suo inizio appena c'è.
  const sheetOpen = cooking && pantry !== undefined;
  const sheetRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (sheetOpen && sheetRef.current) revealAtTop(sheetRef.current);
  }, [sheetOpen]);

  // L'esito compare in cima al dettaglio, mentre chi ha appena toccato «Ho
  // cucinato» è ancora là in fondo dov'era il pulsante: chi non lo vede cucina due
  // volte. Si porta in vista e prende il fuoco, così lo screen reader lo legge anche
  // se la regione `status` è nata insieme al suo testo. Il fuoco senza scorrimento,
  // perché quello istantaneo del fuoco interromperebbe quello animato.
  const outcomeRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (!lastCook || !outcomeRef.current) return;
    outcomeRef.current.focus({ preventScroll: true });
    revealAtTop(outcomeRef.current);
  }, [lastCook]);

  // «Salvata» in vista: si arriva dal pulsante in fondo al modulo, e la pagina nuova non
  // riparte dall'alto da sola
  const savedRef = useRef<HTMLParagraphElement>(null);
  const hasRecipe = recipe !== undefined;
  useEffect(() => {
    if (justSaved && hasRecipe && savedRef.current) revealAtTop(savedRef.current);
  }, [justSaved, hasRecipe]);

  if (isRecipeLoading) return <p className="p-4 text-ink-soft">Carico…</p>;

  // un caricamento fallito non è una ricetta vuota: dirlo sarebbe una bugia su
  // cosa serve e cosa si ha
  if (isRecipeError || !recipe) {
    // una ricetta che non c'è più — un link vecchio, o rifatta dall'import dopo un
    // annullamento — risponde 404: «Riprova» non potrebbe mai riuscire, e l'uscita è il
    // ricettario (come la scheda di un ingrediente unito a un altro, IngredientScreen)
    if (recipeError instanceof ApiError && recipeError.status === 404) {
      return (
        <div className="flex flex-col items-start gap-3 p-4">
          <Alert>Questa ricetta non c'è più.</Alert>
          <Link to="/ricette" className={buttonClasses("secondary")}>
            Torna al ricettario
          </Link>
        </div>
      );
    }
    return (
      <div className="flex flex-col items-start gap-3 p-4">
        <Alert>Non sono riuscito a caricare questa ricetta. Riprova.</Alert>
        <button
          type="button"
          onClick={() => void refetchRecipe()}
          className={buttonClasses("secondary")}
        >
          Riprova
        </button>
      </div>
    );
  }

  // Una ricetta eliminata, aperta da un collegamento vecchio: «Ripristina» e
  // nient'altro — niente «Cucina», niente «Modifica» (R10 §6.1).
  if (recipe.archived_at !== null) {
    return (
      <div className="px-4 pt-2 pb-4">
        <BackLink to="/ricette" label="Ricette" />
        <h1 className="text-2xl font-semibold tracking-tight">{recipe.title}</h1>
        <p className="pt-2 text-ink-soft">Questa ricetta è stata eliminata.</p>
        <button
          type="button"
          onClick={() => restore.mutate()}
          disabled={restore.isPending}
          className={`${buttonClasses("primary", "block")} mt-4`}
        >
          {restore.isPending ? "Ripristino…" : "Ripristina"}
        </button>
        {restore.isError && (
          <Alert className="pt-2">Non sono riuscito a ripristinarla. Riprova.</Alert>
        )}
      </div>
    );
  }

  const primary = recipe.ingredients.filter((line) => line.role === "primary");
  const secondary = recipe.ingredients.filter((line) => line.role === "secondary");
  const groups: { label: string; lines: RecipeIngredientLine[] }[] = [
    { label: "Principali", lines: primary },
    { label: "Secondari", lines: secondary },
  ];

  return (
    <div className="px-4 pt-2 pb-4">
      <BackLink to="/ricette" label="Ricette" />
      {justSaved && (
        // `scroll-mt-16`: l'intestazione fissa (h-12) più un respiro, come l'esito
        // della cottura; `tabIndex={-1}` per il fuoco dato dal codice, non dal Tab
        <p
          ref={savedRef}
          role="status"
          tabIndex={-1}
          className="mb-3 scroll-mt-16 rounded-card bg-brand-tint px-3 py-2.5 text-sm text-brand"
        >
          Salvata.
        </p>
      )}
      <RecipeImage
        url={recipe.image_url}
        alt={recipe.title}
        className="mb-3 aspect-[3/2] w-full rounded-card object-cover"
      />
      <h1 className="text-2xl font-semibold tracking-tight">{recipe.title}</h1>
      {recipe.description && <p className="pt-1 text-ink-soft">{recipe.description}</p>}

      {/* L'attribuzione a un tocco. Solo se la provenienza è davvero un indirizzo:
          per le ricette del seme `source_ref` è una nota («seme iniziale»), e un
          collegamento a quella sarebbe un collegamento rotto.
          `rel="noreferrer"` perché il sito di origine non ha bisogno di sapere da
          dove arriva la visita. */}
      {recipe.source_ref?.startsWith("http") && (
        <a
          href={recipe.source_ref}
          target="_blank"
          rel="noreferrer"
          className="text-sm font-medium text-brand"
        >
          Apri l'originale
        </a>
      )}

      <div className="flex items-center gap-2 pt-2">
        <span className="text-sm text-ink-soft">Costo</span>
        <CostPicker
          value={recipe.cost}
          onChange={(cost) => setCost.mutate(cost)}
          disabled={setCost.isPending}
        />
        {recipe.cost === null && <span className="text-sm text-ink-faint">non indicato</span>}
      </div>
      {setCost.isError && (
        <Alert>Non sono riuscito a salvare il costo: è rimasto quello di prima. Riprova.</Alert>
      )}

      {/* `scroll-mt-12` è l'altezza dell'intestazione fissa (h-12 in AppHeader):
          senza, l'inizio del foglio finirebbe sotto l'header. Lo spazio fra i due
          lo dà già il `pt-4` di questo contenitore. */}
      {sheetOpen ? (
        <div ref={sheetRef} className="scroll-mt-12 pt-4">
          <CookSheet
            recipe={recipe}
            pantryItems={pantry}
            onDone={(result) => {
              if (result) setLastCook(result);
              setCooking(false);
            }}
          />
        </div>
      ) : (
        <>
          {lastCook && (
            // `tabIndex={-1}`: raggiungibile dal fuoco dato dal codice, non dal
            // tasto Tab. `scroll-mt-16`: l'header (h-12) più un respiro, perché
            // lo scorrimento allinea il bordo del riquadro e il suo `mt-3` non conta
            <p
              ref={outcomeRef}
              role="status"
              tabIndex={-1}
              className="mt-3 scroll-mt-16 rounded-card bg-brand-tint px-3 py-2.5 text-sm text-brand"
            >
              {cookNote(lastCook)}
            </p>
          )}

          {/* lo stepper compare solo se la ricetta dichiara le sue porzioni: senza
              quelle non c'è una base da cui riscalare, e mostrarlo comunque
              inviterebbe a un calcolo che qui non si fa */}
          {recipe.servings != null && (
            <div className="pt-3">
              <ServingsStepper value={servings ?? recipe.servings} onChange={setServings} />
            </div>
          )}

          {groups.map(({ label, lines }) => (
            <section key={label}>
              <SectionHeading>{label}</SectionHeading>
              <Card pad={false}>
                <ul className="divide-y divide-line">
                  {lines.map((line) => (
                    <li
                      key={line.ingredient_id}
                      className="flex items-baseline justify-between gap-2 px-3 py-2.5"
                    >
                      <span>
                        {line.ingredient_name}
                        {line.quantity_display && (
                          <span className="ml-2 text-sm text-ink-faint">
                            {line.quantity_display}
                          </span>
                        )}
                      </span>
                      {/* gli stessi due colori della dispensa: il verdetto per riga è
                          la stessa regola primario/secondario vista ingrediente per
                          ingrediente */}
                      <span
                        className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                          line.satisfied ? "bg-brand-tint text-brand" : "bg-low-tint text-low"
                        }`}
                      >
                        {statusNote(line)}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ))}

          {recipe.unscalable_lines > 0 && (
            <p className="px-1 pt-2 text-sm text-ink-faint">
              {/* il denominatore è quante dosi ha la ricetta, non quanti
                  ingredienti: una riga senza dose non è una dose mancata, e il
                  conto lo fa il backend, che sa quali righe una dose ce l'hanno */}
              {recipe.unscalable_lines === 1
                ? `1 dose su ${recipe.dose_lines} non si riscala: resta com'è.`
                : `${recipe.unscalable_lines} dosi su ${recipe.dose_lines} non si riscalano: restano come sono.`}
            </p>
          )}

          <section>
            <SectionHeading>Procedimento</SectionHeading>
            {/* leggere mentre si cucina: interlinea larga, perché si torna a cercare
                il punto in cui si era con le mani sporche e lo sguardo di sbieco */}
            <Card>
              <p className="leading-relaxed whitespace-pre-line">{recipe.instructions}</p>
            </Card>
          </section>

          {/* "Cucina" apre il foglio di cottura, che ha bisogno della dispensa per
              elencare i vasetti concreti: senza quella, il pulsante dice perché non
              si può procedere invece di aprire un foglio vuoto e muto */}
          {isPantryError ? (
            <div className="mt-6 flex flex-col items-start gap-3">
              <Alert>
                Non sono riuscito a caricare la dispensa: non posso avviare la cottura.
              </Alert>
              <button
                type="button"
                onClick={() => void refetchPantry()}
                className={buttonClasses("secondary")}
              >
                Riprova
              </button>
            </div>
          ) : (
            <>
              <button
                type="button"
                // un esito vecchio non deve sopravvivere alla cottura successiva
                onClick={() => {
                  setLastCook(null);
                  setCooking(true);
                }}
                disabled={isPantryLoading}
                className={`${buttonClasses("primary", "block")} mt-6`}
              >
                Cucina
              </button>
              {/* un pulsante grigio e muto non si spiega da sé: dire che manca la
                  dispensa costa una riga e toglie l'unico dubbio */}
              {isPantryLoading && (
                <p className="pt-2 text-xs text-ink-soft">Carico la dispensa…</p>
              )}
            </>
          )}

          {/* due azioni secondarie sotto «Cucina» (R10 §6.1): si correggono o si
              tolgono ricette di rado, e non devono competere con il gesto principale */}
          <div className="mt-3 flex flex-wrap gap-2">
            <Link to={`/ricette/${id}/modifica`} className={buttonClasses("secondary")}>
              Modifica
            </Link>
            <button
              type="button"
              onClick={() => archive.mutate()}
              disabled={archive.isPending}
              className={buttonClasses("danger")}
            >
              {archive.isPending ? "Elimino…" : "Elimina"}
            </button>
          </div>
          {archive.isError && (
            <Alert className="pt-2">
              Non sono riuscito a eliminarla: è ancora nel ricettario. Riprova.
            </Alert>
          )}
        </>
      )}
    </div>
  );
}
