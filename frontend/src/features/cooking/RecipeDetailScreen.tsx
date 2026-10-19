import { useEffect, useRef, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { fetchRecipe, setRecipeArchived, type RecipeScale } from "../recipes/api";
import { fetchPantry } from "../pantry/api";
import { ApiError } from "../../api/client";
import { AddMissingButton } from "./AddMissingButton";
import { AnchorField } from "./AnchorField";
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
  IconSparkles,
  IconTrash,
} from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import { BackLink } from "../../components/BackLink";
import { OriginLink } from "../ai-variant/OriginLink";
import { VariantPrompt } from "../ai-variant/VariantPrompt";
import { VARIANT_PANEL_ID } from "../ai-variant/variantState";
import { RecipeImage } from "../recipes/RecipeImage";
import { useArchiveRecipe } from "../recipes/useArchiveRecipe";
import { revealAtTop } from "../../lib/revealAtTop";
import { capitalizeFirst } from "../../lib/text";
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

/** Com'è finita una richiesta di riscalare da una dose (R2): la vista è cambiata, il
 * server l'ha rifiutata (e dice perché), oppure nel frattempo chi la chiedeva ha fatto
 * altro e la risposta non conta più. */
type AnchorOutcome =
  | { kind: "applied" }
  | { kind: "refused"; problem: string }
  | { kind: "dropped" };

/** Una riga d'ingrediente: il pallino dello stato, il nome, la dose.
 *
 * Il verdetto non si calcola qui: `availability` e `satisfied` arrivano dal server, che
 * ha la regola primario/secondario (`backend/app/domain/rules.py`). «non basta» è il
 * solo caso in cui il colore non dice abbastanza — un principale quasi finito è giallo
 * come un secondario quasi finito, ma a questa ricetta non basta — e sta scritto,
 * piccolo, accanto al nome (Mattia). Il nome del pallino resta quello del vocabolario
 * (`STATUS_LABELS`); «non basta» lo sente anche chi ascolta, perché è testo. */
function IngredientRow({
  line,
  anchoredAmount,
  open,
  onOpen,
  onClose,
  onAnchor,
}: {
  line: RecipeIngredientLine;
  /** La dose fissata su questa riga, se è lei l'ancora (R2), come la manda il server. */
  anchoredAmount: string | null;
  /** Se il campo «Quanto ne fai?» di questa riga è aperto: uno alla volta. */
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  /** Riscala da questa riga: se è fatto, se il server ha rifiutato (col perché), o se
   * nel frattempo il campo è stato chiuso o superato e la risposta non conta più. */
  onAnchor: (amount: string) => Promise<AnchorOutcome>;
}) {
  // la dose toccabile riprende il fuoco quando il campo si chiude, da «Annulla» o da una
  // riscala riuscita: il campo che lo aveva si smonta, e il fuoco cadrebbe sul `body`
  const doseRef = useRef<HTMLButtonElement>(null);
  return (
    <li className="px-3 py-2.5">
      <div className="flex items-center gap-2.5">
        <StatusDot availability={line.availability} />
        <span className="min-w-0 flex-1">
          {/* la maiuscola solo a video (spec T3 §4.7): apre la riga, non è dentro una
              frase né in un nome accessibile */}
          <span>{capitalizeFirst(line.ingredient_name)}</span>
          {line.availability === "low" && !line.satisfied && (
            <span className="ml-2 text-xs font-medium text-low">non basta</span>
          )}
          {/* la nota della riga: le parole che l'import scriveva davanti alla dose («da
              grattugiare», «36 mesi»), o quella scritta a mano. Sotto il nome e piccola:
              dice com'è l'ingrediente, non quanto — la dose resta a destra */}
          {line.note && (
            <span className="block break-words text-xs text-ink-soft">{line.note}</span>
          )}
        </span>
        {line.quantity_display &&
          (line.anchorable ? (
            // R2, secondo modo: una dose che si riscala si tocca. Un pulsante leggero,
            // sottolineato a puntini (il segno che si tocca), alto 44 px senza alzare la
            // riga (`-my-2.5` restituisce il `py-2.5` della riga); `-mr-3` riporta il testo
            // verso il bordo, dove stanno le dosi che non si toccano. La dose fissata in
            // grassetto dentro un `<strong>`: una seconda classe di colore o di peso sul
            // pulsante litigherebbe con quella di `ghost` nel CSS compilato
            <Button
              ref={doseRef}
              variant="ghost"
              accessibleName={`${line.quantity_display}: riscala da ${line.ingredient_name}`}
              aria-expanded={open}
              onClick={open ? onClose : onOpen}
              className="-my-2.5 -mr-3 shrink-0 underline decoration-dotted underline-offset-4"
            >
              {anchoredAmount !== null ? (
                <strong className="font-semibold text-ink">{line.quantity_display}</strong>
              ) : (
                line.quantity_display
              )}
            </Button>
          ) : (
            <span className="shrink-0 text-sm text-ink-faint">{line.quantity_display}</span>
          ))}
      </div>
      {open && (
        <AnchorField
          unit={line.anchor_unit}
          initial={anchoredAmount?.replace(".", ",") ?? ""}
          onSubmit={async (amount) => {
            const outcome = await onAnchor(amount);
            // il fuoco torna alla dose solo se la vista è davvero cambiata: se il campo
            // era già chiuso, o ce n'è un altro aperto, il fuoco sta dove l'ha messo chi
            // scrive. `null` anche per «dropped»: il campo che aspetta è già smontato
            if (outcome.kind === "applied") doseRef.current?.focus();
            return outcome.kind === "refused" ? outcome.problem : null;
          }}
          onCancel={() => {
            onClose();
            doseRef.current?.focus();
          }}
        />
      )}
    </li>
  );
}

/** `key={id}`: da una variante alla sua originale (R8) la rotta resta la stessa e cambia
 * solo `:id`. Senza la chiave React terrebbe lo stato della ricetta di prima — le porzioni
 * scelte, il foglio della cottura o il pannello della variante aperti — e lo applicherebbe
 * all'altra. */
export function RecipeDetailScreen() {
  const { id = "" } = useParams();
  return <RecipeDetailView key={id} id={id} />;
}

function RecipeDetailView({ id }: { id: string }) {
  const [cooking, setCooking] = useState(false);

  // come si vuole vedere la ricetta: per porzioni, o da una dose fissata su una riga
  // (R2, secondo modo). Un modo alla volta, ed è una vista: non si salva, e uscire
  // dalla ricetta se ne dimentica — è quel che vuole chi guarda cosa cucinare stasera.
  // `null` è la ricetta com'è.
  const [scale, setScale] = useState<RecipeScale | null>(null);
  // la riga il cui campo «Quanto ne fai?» è aperto: uno alla volta
  const [anchorField, setAnchorField] = useState<string | null>(null);
  // quante volte il campo aperto è cambiato (aperto, chiuso, passato a un'altra riga, o
  // la vista cambiata da un altro gesto): una richiesta di riscalare ricorda quella che
  // c'era quando è partita, e se al ritorno non è più la stessa non tocca la vista. Una
  // numerazione e non il nome della riga: chiudere e riaprire la stessa riga è un altro
  // campo, e la risposta del primo non è più sua
  const fieldEpoch = useRef(0);
  function changeAnchorField(next: string | null) {
    fieldEpoch.current += 1;
    setAnchorField(next);
  }

  // R8: il pannello di «Modifica con AI», e il tasto che lo apre. Chiuso il pannello il
  // fuoco torna sul tasto: il pannello si smonta col campo che aveva il fuoco.
  const [variantOpen, setVariantOpen] = useState(false);
  const variantButtonRef = useRef<HTMLButtonElement>(null);

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
    queryKey: ["recipe", id, scale],
    queryFn: () => fetchRecipe(id, scale ?? undefined),
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
    isFetching: isPantryFetching,
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
  const retryPantryRef = useRef<HTMLButtonElement>(null);
  const refocusCook = useRef(false);
  // Se la dispensa non si ricarica, al posto di «Cucina» c'è l'avviso con «Riprova», e il
  // fuoco va lì — anche se l'errore arriva dopo, a fuoco già tornato su «Cucina», che
  // sparendo lo lascia sul `body` (T3 Consegna 5). L'intenzione resta finché la rilettura
  // della dispensa non è finita. Solo se il fuoco è caduto sulla pagina: chi nel frattempo
  // ha toccato altro se lo tiene.
  useEffect(() => {
    if (sheetOpen || !refocusCook.current) return;
    const active = document.activeElement;
    if (active === null || active === document.body) {
      (isPantryError ? retryPantryRef.current : cookRef.current)?.focus();
    }
    if (!isPantryFetching) refocusCook.current = false;
  }, [sheetOpen, isPantryError, isPantryFetching]);

  // R2, secondo modo: si chiede prima la ricetta riscalata, e solo se il server la dà
  // la vista cambia. Un 422 (oltre le 50 volte) resta così sotto il campo, con la
  // frase del server, e la ricetta resta com'era: cambiare vista e scoprire dopo il
  // rifiuto avrebbe mandato lo schermo intero nel ramo d'errore. La risposta finisce
  // nella cache con la chiave della query qui sopra, che la trova già pronta (e la
  // rilegge in sottofondo, come ogni dato vecchio).
  async function anchorOn(ingredientId: string, amount: string): Promise<AnchorOutcome> {
    const next: RecipeScale = { anchor: ingredientId, amount };
    // «Annulla» resta attivo mentre la richiesta è in volo (il server può metterci
    // qualche secondo): chi ha annullato, aperto un'altra riga o toccato lo stepper ha
    // già scelto, e una risposta arrivata dopo non deve disfare la sua scelta. La
    // risposta resta in cache, innocua
    const epoch = fieldEpoch.current;
    try {
      await queryClient.fetchQuery({
        queryKey: ["recipe", id, next],
        queryFn: () => fetchRecipe(id, next),
      });
    } catch (error) {
      if (fieldEpoch.current !== epoch) return { kind: "dropped" };
      if (error instanceof ApiError && error.status === 422) {
        const detail = (error.body as { detail?: unknown } | null)?.detail;
        if (typeof detail === "string") return { kind: "refused", problem: detail };
      }
      return { kind: "refused", problem: "Non sono riuscito a riscalare. Riprova." };
    }
    if (fieldEpoch.current !== epoch) return { kind: "dropped" };
    changeAnchorField(null);
    setScale(next);
    return { kind: "applied" };
  }

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
    // Una vista riscalata già accettata che il server ora rifiuta: la ricetta è stata
    // modificata altrove e la dose è uscita dalle 50 volte. «Riprova» rifarebbe la stessa
    // domanda; l'uscita è la ricetta com'è.
    if (
      recipeError instanceof ApiError &&
      recipeError.status === 422 &&
      scale !== null &&
      "anchor" in scale
    ) {
      return (
        <div className="flex flex-col items-start gap-3 p-4">
          <Alert>Non riesco più a riscalare da quella dose: la ricetta è cambiata.</Alert>
          <Button
            onClick={() => {
              // anche il campo aperto e una riscala in volo cadono: tornano alla ricetta
              changeAnchorField(null);
              setScale(null);
            }}
          >
            Torna alle dosi della ricetta
          </Button>
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
  // la dose fissata, se la vista è riscalata da un ingrediente (R2). `?? null`: una
  // risposta di un backend vecchio, in cache nel service worker, non ha il campo
  const anchor = recipe.anchor ?? null;
  const anchorLine =
    anchor === null
      ? null
      : (recipe.ingredients.find((line) => line.ingredient_id === anchor.ingredient_id) ??
        null);

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
          {/* R8: fra le due azioni rare, perché è una modifica; la scintilla è l'icona di
              «scrivi con l'AI» (spec T3 §3.3) */}
          <Button
            ref={variantButtonRef}
            variant="ghost"
            icon={IconSparkles}
            label="Modifica con AI"
            aria-expanded={variantOpen}
            aria-controls={VARIANT_PANEL_ID}
            onClick={() => setVariantOpen((open) => !open)}
          />
          <Button
            variant="ghost"
            icon={IconTrash}
            label="Elimina"
            busy={archiving}
            onClick={() => archive({ id: recipe.id, title: recipe.title })}
          />
        </IconToolbar>
      </div>

      {/* R8, Mattia: nella variante, sotto il titolo, la ricetta da cui nasce */}
      {recipe.derived_from && <OriginLink origin={recipe.derived_from} />}

      {variantOpen && (
        <VariantPrompt
          recipe={recipe}
          onClose={() => {
            setVariantOpen(false);
            variantButtonRef.current?.focus();
          }}
        />
      )}

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
          {/* sempre, anche senza porzioni: allora dice perché è fermo. Con una dose
              fissata dice le porzioni che fa, «≈ 1,5», e toccarlo torna alle porzioni
              intere (R2: un modo alla volta) */}
          <div className="pt-3">
            <ServingsStepper
              value={
                recipe.servings === null
                  ? null
                  : scale !== null && "servings" in scale
                    ? scale.servings
                    : recipe.servings
              }
              approx={anchor?.equivalent_servings ?? null}
              onChange={(next) => {
                changeAnchorField(null);
                setScale({ servings: next });
              }}
            />
            {anchorLine !== null && (
              // da quale dose è riscalata, e l'uscita: sulle ricette senza porzioni − e +
              // sono spenti, e sarebbe l'unica strada per tornare indietro
              <div className="flex flex-wrap items-center gap-x-2 pt-1">
                <p className="text-sm text-ink-soft">
                  Riscalata da {anchorLine.ingredient_name}: {anchorLine.quantity_display}.
                </p>
                <Button
                  variant="ghost"
                  onClick={() => {
                    changeAnchorField(null);
                    setScale(null);
                  }}
                >
                  Torna alle dosi della ricetta
                </Button>
              </div>
            )}
          </div>

          {groups.map(({ label, lines }) => (
            <section key={label}>
              <SectionHeading>{label}</SectionHeading>
              {/* niente linee fra le righe (spec T3 §2): lo spazio basta */}
              <Card pad={false}>
                <ul>
                  {lines.map((line) => (
                    <IngredientRow
                      key={line.ingredient_id}
                      line={line}
                      anchoredAmount={
                        anchor !== null && anchor.ingredient_id === line.ingredient_id
                          ? anchor.amount
                          : null
                      }
                      open={anchorField === line.ingredient_id}
                      onOpen={() => changeAnchorField(line.ingredient_id)}
                      onClose={() => changeAnchorField(null)}
                      onAnchor={(amount) => anchorOn(line.ingredient_id, amount)}
                    />
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
                {/* `busy` mentre rilegge: il fuoco, che può essere arrivato qui dopo
                    «Ho cucinato», resta qui */}
                <Button
                  ref={retryPantryRef}
                  busy={isPantryFetching}
                  onClick={() => {
                    // Se la rilettura riesce «Riprova» sparisce e il fuoco cadrebbe sulla
                    // pagina: l'intenzione si riarma, e l'effetto lo porta su «Cucina» (o
                    // di nuovo su «Riprova» se fallisce ancora) — sempre e solo se è
                    // caduto sulla pagina.
                    refocusCook.current = true;
                    void refetchPantry();
                  }}
                >
                  Riprova
                </Button>
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
                onClick={() => {
                  // il foglio copre la ricetta: il campo aperto si chiude e una riscala
                  // in volo si lascia cadere, o la vista cambierebbe sotto il foglio e
                  // chi cuoce manderebbe un'ancora da una vista mai vista cambiare
                  changeAnchorField(null);
                  setCooking(true);
                }}
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
