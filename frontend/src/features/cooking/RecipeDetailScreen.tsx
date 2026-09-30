import { useEffect, useRef, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { fetchRecipe, setRecipeArchived } from "../recipes/api";
import { fetchPantry } from "../pantry/api";
import { ApiError } from "../../api/client";
import { AddMissingButton } from "./AddMissingButton";
import { CookSheet } from "./CookSheet";
import { ServingsStepper } from "./ServingsStepper";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { CostMeter } from "../../components/ui/CostMeter";
import { IconToolbar } from "../../components/ui/IconToolbar";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { StatusDot } from "../../components/ui/StatusDot";
import { buttonClasses } from "../../components/ui/buttonClasses";
import {
  IconChefHat,
  IconChevronLeft,
  IconExternalLink,
  IconPencil,
  IconRestore,
  IconTrash,
} from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import { BackLink } from "../../components/BackLink";
import { RecipeImage } from "../recipes/RecipeImage";
import { useArchiveRecipe } from "../recipes/useArchiveRecipe";
import { revealAtTop } from "../../lib/revealAtTop";
import type { CookResult, RecipeDetail, RecipeIngredientLine } from "../../domain/types";

// Il numero viene dal backend, non da un conteggio fatto qui: quante voci sono
// tornate in lista lo sa solo chi ha applicato le transizioni (una lista può già
// contenere quell'ingrediente, e allora non si duplica).
function cookNote(result: CookResult): string {
  if (result.restocked === 0) return "Segnato. Niente è tornato in lista della spesa.";
  if (result.restocked === 1) return "Segnato. Una cosa è tornata in lista della spesa.";
  return `Segnato. ${result.restocked} cose sono tornate in lista della spesa.`;
}

/** In cima al dettaglio: il ritorno al ricettario e, se c'è, la foto (spec T3 §4.6).
 *
 * Il tasto sta nel flusso e la foto gli scivola sotto con un margine negativo, alto
 * quanto il tasto più il suo margine (44 + 8 px): così, se la foto non c'è o non carica
 * — `RecipeImage` allora non disegna niente — il tasto resta al suo posto sopra il
 * titolo, senza che questo schermo debba sapere se l'immagine è arrivata. `relative`
 * lo dipinge sopra la foto, che non è posizionata, senza uno `z-index` che litighi con
 * l'intestazione fissa. Il fondo è pieno (`bg-card`): sopra una foto un testo senza
 * fondo avrebbe il contrasto della foto, cioè nessuno garantito. «Ricette» e non
 * `navigate(-1)`, per il motivo scritto in `BackLink`. */
function RecipeHero({ recipe }: { recipe: RecipeDetail }) {
  return (
    <div>
      <Link
        to="/ricette"
        className="relative mt-2 ml-2 flex min-h-11 w-fit items-center gap-1 rounded-full bg-card py-2 pr-4 pl-2.5 text-sm font-medium text-ink ring-1 ring-line ring-inset"
      >
        <IconChevronLeft aria-hidden="true" className="size-5" stroke={1.8} />
        Ricette
      </Link>
      <RecipeImage
        url={recipe.image_url}
        alt={recipe.title}
        className="-mt-[3.25rem] block aspect-[3/2] w-full rounded-card object-cover"
      />
    </div>
  );
}

/** Una riga d'ingrediente: il pallino dello stato, il nome, la dose.
 *
 * Il verdetto non si calcola qui: `availability` e `satisfied` arrivano dal server, che
 * ha la regola primario/secondario (`backend/app/domain/rules.py`). «non basta» è il
 * solo caso in cui il colore non dice abbastanza — un principale quasi finito è giallo
 * come un secondario quasi finito, ma a questa ricetta non basta — e sta scritto,
 * piccolo, accanto al nome (Mattia). Il nome del pallino resta quello del vocabolario
 * (`STATUS_LABELS`); «non basta» lo sente anche chi ascolta, perché è testo. */
function IngredientRow({ line }: { line: RecipeIngredientLine }) {
  return (
    <li className="flex items-center gap-2.5 px-3 py-2.5">
      <StatusDot availability={line.availability} />
      <span className="min-w-0 flex-1">
        <span>{line.ingredient_name}</span>
        {line.availability === "low" && !line.satisfied && (
          <span className="ml-2 text-xs font-medium text-low">non basta</span>
        )}
      </span>
      {line.quantity_display && (
        <span className="shrink-0 text-sm text-ink-faint">{line.quantity_display}</span>
      )}
    </li>
  );
}

export function RecipeDetailScreen() {
  const { id = "" } = useParams();
  const [cooking, setCooking] = useState(false);

  // le porzioni chieste: è una vista, non si salva. Uscire dalla ricetta se ne
  // dimentica, ed è quel che vuole chi sta guardando cosa cucinare stasera.
  const [servings, setServings] = useState<number | null>(null);

  const queryClient = useQueryClient();
  const notice = useNotice();
  // «Elimina» archivia subito, senza chiedere: la conferma è l'avviso con «Annulla»
  // (Piano 2, spec T3 §3.5), e il gancio porta al ricettario
  const { archive, pending: archiving } = useArchiveRecipe();

  // Ripristinare cambia cosa elencano ricettario e filtro per categoria, oltre al
  // dettaglio stesso: si rinfrescano tutti e tre.
  const restore = useMutation({
    mutationFn: () => setRecipeArchived(id, false),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ["recipe", id] }),
        queryClient.invalidateQueries({ queryKey: ["recipes"] }),
        queryClient.invalidateQueries({ queryKey: ["recipe-categories"] }),
      ]),
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

  // Il foglio prende il posto di ciò che sta sotto la testa, e l'inizio del foglio —
  // con «Tocca solo ciò che è cambiato» — può restare fuori vista: si porta in vista
  // appena c'è.
  const sheetOpen = cooking && pantry !== undefined;
  const sheetRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (sheetOpen && sheetRef.current) revealAtTop(sheetRef.current);
  }, [sheetOpen]);

  // Chiuso il foglio — cucinato o annullato — il fuoco torna su «Cucina»: il foglio si
  // è smontato col pulsante che aveva il fuoco, che altrimenti finirebbe sul `body`, e
  // l'esito lo dice l'avviso unico, che il fuoco non lo prende. Un `ref` e non uno
  // stato: è un'intenzione per il prossimo disegno, non qualcosa da disegnare.
  const cookRef = useRef<HTMLButtonElement>(null);
  const refocusCook = useRef(false);
  useEffect(() => {
    if (sheetOpen || !refocusCook.current) return;
    refocusCook.current = false;
    cookRef.current?.focus();
  }, [sheetOpen]);

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
        <Button
          variant="primary"
          shape="block"
          icon={IconRestore}
          busy={restore.isPending}
          onClick={() => restore.mutate()}
          className="mt-4"
        >
          {restore.isPending ? "Ripristino…" : "Ripristina"}
        </Button>
        {restore.isError && (
          <Alert className="pt-2">Non sono riuscito a ripristinarla. Riprova.</Alert>
        )}
      </div>
    );
  }

  const groups: { label: string; lines: RecipeIngredientLine[] }[] = [
    { label: "Principali", lines: recipe.ingredients.filter((line) => line.role === "primary") },
    { label: "Secondari", lines: recipe.ingredients.filter((line) => line.role === "secondary") },
  ].filter((group) => group.lines.length > 0);
  // quali righe mancano lo dice il server (`satisfied`): qui si filtra, non si giudica
  const missing = recipe.ingredients.filter((line) => !line.satisfied);

  return (
    <div className="px-4 pt-2 pb-4">
      <RecipeHero recipe={recipe} />

      {/* le due azioni rare accanto al titolo, di sola icona (spec T3 §2): si correggono
          o si tolgono ricette di rado, e non devono competere con «Cucina». `ghost` anche
          «Elimina»: il rosso vuol dire «manca» e «non è andata» (spec §3.1) */}
      <div className="flex items-start gap-2 pt-3">
        <h1 className="min-w-0 flex-1 pt-1.5 text-2xl font-semibold tracking-tight">
          {recipe.title}
        </h1>
        <IconToolbar label="Azioni della ricetta">
          <Link
            to={`/ricette/${recipe.id}/modifica`}
            aria-label="Modifica"
            className={buttonClasses("ghost", "icon")}
          >
            <IconPencil aria-hidden="true" className="size-5" stroke={1.8} />
          </Link>
          <Button
            variant="ghost"
            icon={IconTrash}
            label="Elimina"
            busy={archiving}
            onClick={() => archive({ id: recipe.id, title: recipe.title })}
          />
        </IconToolbar>
      </div>

      {/* categoria e costo da leggere: il costo si cambia da «Modifica» (dal giro, un
          tocco scorrendo sui € lo cambiava) */}
      {(recipe.category || recipe.cost !== null) && (
        <p className="flex items-center gap-2 pt-1 text-sm text-ink-soft">
          {recipe.category && <span>{recipe.category}</span>}
          {recipe.category && recipe.cost !== null && <span aria-hidden="true">·</span>}
          <CostMeter cost={recipe.cost} />
        </p>
      )}
      {recipe.description && <p className="pt-2 text-ink-soft">{recipe.description}</p>}

      {/* L'attribuzione a un tocco, alta 44 px (dal giro: era alta 19). Solo se la
          provenienza è davvero un indirizzo: per le ricette del seme `source_ref` è una
          nota («seme iniziale»), e un collegamento a quella sarebbe un collegamento
          rotto. `rel="noreferrer"` perché il sito di origine non ha bisogno di sapere
          da dove arriva la visita. */}
      {recipe.source_ref?.startsWith("http") && (
        <a
          href={recipe.source_ref}
          target="_blank"
          rel="noreferrer"
          className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-brand"
        >
          <IconExternalLink aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
          Apri l'originale
        </a>
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
              // l'esito passa dall'avviso unico (T4): lo stesso testo di prima, in un
              // punto fisso, visibile da dovunque si sia scorsi
              if (result) notice({ text: cookNote(result) });
              refocusCook.current = true;
              setCooking(false);
            }}
          />
        </div>
      ) : (
        <>
          {/* sempre, anche senza porzioni: allora dice perché è fermo */}
          <div className="pt-3">
            <ServingsStepper
              value={recipe.servings === null ? null : (servings ?? recipe.servings)}
              onChange={setServings}
            />
          </div>

          {groups.map(({ label, lines }) => (
            <section key={label}>
              <SectionHeading>{label}</SectionHeading>
              {/* niente linee fra le righe (spec T3 §2): lo spazio basta */}
              <Card pad={false}>
                <ul>
                  {lines.map((line) => (
                    <IngredientRow key={line.ingredient_id} line={line} />
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

          {/* «Cucina» in fondo agli ingredienti, prima del procedimento (dal giro: sotto
              il procedimento sembrava dire «inizia a cucinare»), e sotto di lui la
              freccia ricetta → lista. Uno sotto l'altro e non affiancati: a 375 px i due
              testi con le icone non ci stanno su una riga */}
          <div className="mt-6 flex flex-col gap-2">
            {isPantryError ? (
              // il foglio ha bisogno della dispensa per elencare i vasetti concreti:
              // senza, il posto di «Cucina» dice perché non si può procedere invece di
              // aprire un foglio vuoto e muto
              <div className="flex flex-col items-start gap-3">
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
              <Button
                ref={cookRef}
                variant="primary"
                shape="block"
                icon={IconChefHat}
                // «non ancora», col perché scritto sotto (regola del Piano 1): un
                // pulsante grigio e muto non si spiega da sé
                unavailableReason={isPantryLoading ? "Carico la dispensa…" : undefined}
                onClick={() => setCooking(true)}
              >
                Cucina
              </Button>
            )}
            <AddMissingButton lines={missing} />
          </div>

          <section>
            <SectionHeading>Procedimento</SectionHeading>
            {/* leggere mentre si cucina: interlinea larga, perché si torna a cercare
                il punto in cui si era con le mani sporche e lo sguardo di sbieco */}
            <Card>
              <p className="leading-relaxed whitespace-pre-line">{recipe.instructions}</p>
            </Card>
          </section>
        </>
      )}
    </div>
  );
}
