import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { createRecipe, draftRecipe } from "../recipes/api";
import { IngredientPicker } from "../../components/IngredientPicker";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { INGREDIENT_CATEGORIES } from "../../domain/categories";
import type {
  DraftIngredient,
  Ingredient,
  IngredientRole,
  RecipeDraft,
} from "../../domain/types";

// I limiti che `RecipeCreate` applica nel backend. Stanno qui per far correggere
// un campo *prima* della chiamata, non per decidere qualcosa: l'autorità resta
// il backend, e un 422 che arriva comunque viene detto per quello che è.
const TITLE_MAX = 200;
const QUANTITY_MAX = 100;
const SOURCE_REF_MAX = 500;
const SERVINGS_MIN = 1;
const SERVINGS_MAX = 50;

const ROLE_LABELS: Record<IngredientRole, string> = {
  primary: "principale",
  secondary: "secondario",
};

/** Una riga di ingrediente del modulo. Le righe proposte dalla bozza e quelle
 * scelte a mano convivono nella stessa lista: cambia solo chi ha proposto
 * l'aggancio, e quello che il backend ha detto di quell'aggancio. */
interface FormLine {
  key: string;
  label: string;
  ingredientId: string | null;
  matchedName: string | null;
  // vero solo per una riga della bozza che il backend ha marcato `confident: false`.
  // Non lo ricalcoliamo: lo riportiamo.
  uncertain: boolean;
  manual: boolean;
  role: IngredientRole;
  quantityText: string;
  included: boolean;
  // `null` quando la riga è agganciata o quando il modello non ha detto niente
  // di utilizzabile. Valorizzato è la ragione per cui una riga senza aggancio
  // può comunque salvarsi: il modello ha detto cos'è e in che reparto, e non
  // c'è nessun aggancio dubbio da verificare.
  proposedCategory: string | null;
}

function lineFromDraft(line: DraftIngredient, index: number): FormLine {
  const attached = line.ingredient_id !== null;
  const uncertain = attached && !line.confident;
  const proposedCategory = attached ? null : line.proposed_category ?? null;
  return {
    // l'indice, non il solo nome: niente vieta al modello di proporre due volte
    // lo stesso `raw_name` (il prompt non lo vieta e `draft_recipe` non deduplica),
    // e due righe con la stessa chiave fanno muovere insieme spunta e quantità
    // delle due — oltre a far scartare una riga a React senza dire niente
    key: `draft:${index}:${line.raw_name}`,
    label: line.raw_name,
    ingredientId: line.ingredient_id,
    matchedName: line.matched_name,
    uncertain,
    manual: false,
    role: line.role,
    quantityText: line.quantity_text ?? "",
    // Un aggancio incerto parte ESCLUSO. Partire incluso lo farebbe entrare nel
    // ricettario senza che nessuno l'abbia guardato, ed è esattamente
    // l'accettazione in silenzio che la seconda decisione di progetto vieta: un
    // ingrediente sbagliato avvelena la disponibilità di ogni ricetta che lo usa.
    // Una riga senza aggancio ma con una categoria proposta è il caso opposto:
    // non c'è nessuna ipotesi da confermare, il modello ha detto cos'è, quindi
    // parte inclusa.
    included: (attached && !uncertain) || proposedCategory !== null,
    proposedCategory,
  };
}

function lineFromIngredient(ingredient: Ingredient): FormLine {
  return {
    key: `manual:${ingredient.id}`,
    label: ingredient.display_name,
    ingredientId: ingredient.id,
    matchedName: ingredient.name,
    // scelto a mano dall'anagrafica: non c'è nessuna ipotesi da confermare
    uncertain: false,
    manual: true,
    // "principale" è il default prudente: un principale esige disponibilità
    // piena, quindi al massimo fa sembrare la ricetta meno cucinabile di
    // quanto sia — mai il contrario. Il ruolo resta cambiabile qui accanto.
    role: "primary",
    quantityText: "",
    included: true,
    proposedCategory: null,
  };
}

function matchNote(line: FormLine): string {
  if (line.ingredientId === null) {
    if (line.proposedCategory !== null) return `${line.label}: da creare salvando`;
    return `${line.label} non in anagrafica, sarà escluso`;
  }
  if (line.uncertain) return `${line.matchedName}, da confermare`;
  return line.matchedName ?? line.label;
}

/** Quello che il backend rifiuterebbe con un 422, detto qui in modo che si possa
 * correggere invece di riprovare a mandare gli stessi dati. `null` quando non
 * c'è niente da sistemare. */
function validationProblem(
  title: string,
  instructions: string,
  servingsText: string,
  savable: FormLine[]
): string | null {
  if (title.trim() === "" || instructions.trim() === "")
    return "Servono un titolo e un procedimento per salvare.";
  if (title.trim().length > TITLE_MAX)
    return `Il titolo è troppo lungo: massimo ${TITLE_MAX} caratteri.`;

  const servings = servingsText.trim();
  if (servings !== "" && !/^\d+$/.test(servings))
    return `Le porzioni vanno scritte come numero intero da ${SERVINGS_MIN} a ${SERVINGS_MAX}, oppure lasciate vuote.`;
  if (servings !== "" && (Number(servings) < SERVINGS_MIN || Number(servings) > SERVINGS_MAX))
    return `Le porzioni devono stare tra ${SERVINGS_MIN} e ${SERVINGS_MAX}. Lascia il campo vuoto se non lo sai: vuoto è meglio di inventato.`;

  const tooLong = savable.find((line) => line.quantityText.trim().length > QUANTITY_MAX);
  if (tooLong)
    return `La quantità di «${tooLong.label}» è troppo lunga: massimo ${QUANTITY_MAX} caratteri.`;

  return null;
}

/** `source_ref` sta in 500 caratteri, il prompt può arrivarne a 1000: la
 * provenienza si accorcia, il testo scritto no — quello resta nel suo campo.
 * Senza questo, un prompt lungo faceva rifiutare il salvataggio con un 422. */
function sourceRef(prompt: string): string {
  const ref = `prompt: ${prompt}`;
  return ref.length <= SOURCE_REF_MAX ? ref : `${ref.slice(0, SOURCE_REF_MAX - 1)}…`;
}

/** Un salvataggio rifiutato per validazione non è un guasto passeggero: mandare
 * di nuovo gli stessi byte darà lo stesso esito, e dire "riprova" sarebbe un
 * vicolo cieco travestito da invito. Il messaggio lo distingue per stato.
 *
 * Il `detail` di un 422 di FastAPI è una lista di oggetti, non una frase: finisce
 * in `ApiError.message` come "[object Object]", quindi non si mostra grezzo. */
function saveProblem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422)
      return "Il backend ha rifiutato la ricetta: qualcosa nei campi qui sopra non va. Correggilo — rimandarla identica darà lo stesso esito.";
    if (error.status === 409)
      return "Due righe puntano allo stesso ingrediente. Togli la spunta a una delle due, poi salva.";
    if (error.status === 404)
      return "Un ingrediente agganciato non esiste più. Togli la spunta a quella riga, poi salva.";
  }
  return "Non sono riuscito a salvare la ricetta. Niente è andato perso: riprova.";
}

// Lo schermo che tiene insieme la dipendenza meno affidabile dell'app e la via
// d'uscita da tutti i suoi guasti. Claude può non rispondere, rispondere con
// qualcosa di inutilizzabile, o proporre un ingrediente che in anagrafica non
// esiste: nessuno di questi casi può diventare una pagina d'errore.
//
// Per questo il modulo della ricetta è SEMPRE in pagina, non dietro un `draft`
// né dietro un `propose.isError`. Tre ragioni, in ordine di peso:
//  1. `createRecipe` non ha nessun altro punto di chiamata nel frontend: se il
//     modulo vive dentro una condizione, scrivere una ricetta a mano è una cosa
//     che l'app non sa fare finché quella condizione non è vera.
//  2. Una via d'uscita che si apre solo dopo un guasto si rompe insieme al
//     guasto: basta sbagliare la condizione e il vicolo cieco torna. Un modulo
//     senza condizioni non ha nessun flag da sbagliare.
//  3. Chiedere all'AI diventa un aiuto sul modulo — precompila i campi — invece
//     di essere il cancello da cui passare per averlo.
export function AiDraftScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [prompt, setPrompt] = useState("");
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  // stringa, non numero: un campo vuoto vuole dire "non lo so", e non deve
  // diventare uno zero o un 4 inventato da noi
  const [servingsText, setServingsText] = useState("");
  const [lines, setLines] = useState<FormLine[]>([]);

  const propose = useMutation({
    mutationFn: () => draftRecipe(prompt),
    onSuccess: (result) => {
      setDraft(result);
      setTitle(result.title);
      setInstructions(result.instructions);
      setServingsText(String(result.servings ?? ""));
      setLines((prev) => [
        ...result.ingredients.map(lineFromDraft),
        // le righe scelte a mano non sono roba del modello: una nuova bozza
        // sostituisce le sue proposte, non il lavoro di chi sta scrivendo
        ...prev.filter((line) => line.manual),
      ]);
    },
  });

  // Una riga si può salvare se è agganciata, o se porta nome e categoria con cui
  // crearla. La seconda forma parte inclusa: non c'è nessun aggancio da verificare,
  // e il selettore della categoria qui sotto è lì per correggerla prima di salvare.
  const savable = lines.filter(
    (line) => line.included && (line.ingredientId !== null || line.proposedCategory !== null)
  );
  const problem = validationProblem(title, instructions, servingsText, savable);

  const save = useMutation({
    mutationFn: () =>
      createRecipe({
        title: title.trim(),
        description: draft?.description ?? null,
        instructions,
        servings: servingsText.trim() === "" ? null : Number(servingsText.trim()),
        // la provenienza dice il vero: senza bozza questa ricetta l'ha scritta
        // una persona, e spacciarla per "ai" sarebbe una bugia nello storico
        source: draft ? "ai" : "manual",
        source_ref: draft ? sourceRef(prompt) : null,
        ingredients: savable.map((line) =>
          line.ingredientId !== null
            ? {
                ingredient_id: line.ingredientId,
                role: line.role,
                // `quantity_text` è testo da mostrare, mai un numero da calcolare:
                // passa verbatim, e vuoto resta vuoto invece di diventare ""
                quantity_text: line.quantityText.trim() === "" ? null : line.quantityText,
              }
            : {
                name: line.label.trim().toLowerCase(),
                category: line.proposedCategory,
                role: line.role,
                quantity_text: line.quantityText.trim() === "" ? null : line.quantityText,
              }
        ),
      }),
    onSuccess: (recipe) => {
      // la ricetta appena scritta deve apparire nel ricettario al prossimo giro:
      // senza invalidare la lista, la ricerca continuerebbe a mostrare dati vecchi
      void queryClient.invalidateQueries({ queryKey: ["recipes"] });
      navigate(`/ricette/${recipe.id}`);
    },
  });

  function updateLine(key: string, change: Partial<FormLine>) {
    setLines((prev) => prev.map((line) => (line.key === key ? { ...line, ...change } : line)));
  }

  function attach(ingredient: Ingredient) {
    setLines((prev) => {
      // due righe sullo stesso ingrediente sono un 409 del backend, e non
      // vorrebbero dire niente: se c'è già, la si include e basta — che è anche
      // il modo di confermare un aggancio incerto scegliendolo di persona
      if (prev.some((line) => line.ingredientId === ingredient.id))
        return prev.map((line) =>
          line.ingredientId === ingredient.id ? { ...line, included: true } : line
        );
      return [...prev, lineFromIngredient(ingredient)];
    });
  }

  return (
    <div className="flex flex-col gap-4 px-4 pt-5 pb-4">
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

      <div className="flex flex-col gap-3 border-t border-line pt-4">
        <label className="text-sm">
          Titolo
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={TITLE_MAX}
            className="mt-1.5"
          />
        </label>

        <label className="text-sm">
          Porzioni
          <input
            aria-label="Porzioni"
            value={servingsText}
            onChange={(e) => setServingsText(e.target.value)}
            inputMode="numeric"
            placeholder="Lascia vuoto se non lo sai"
            className="mt-1.5"
          />
        </label>

        <div>
          <h2 className="text-xs uppercase tracking-wide text-ink-faint">Ingredienti</h2>
          <ul className="divide-y divide-line">
            {lines.map((line) => (
              <li key={line.key} className="flex flex-col gap-2 py-2 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <label className="flex min-h-11 flex-1 items-center gap-3">
                    {/* Stessa condizione del filtro `savable` qui sopra: una riga
                        entra nel salvataggio se è agganciata o se porta nome e
                        categoria con cui crearla, quindi è esattamente lì che deve
                        poter essere esclusa. Lasciarle scostare ha già prodotto un
                        vicolo cieco: una riga "da creare salvando" che
                        collide con un'altra allo stesso ingrediente diventava un 409
                        senza nessuna casella con cui toglierne una. */}
                    {(line.ingredientId !== null || line.proposedCategory !== null) && (
                      <input
                        type="checkbox"
                        aria-label={`Includi ${line.label}`}
                        checked={line.included}
                        onChange={() => updateLine(line.key, { included: !line.included })}
                        className="size-5 shrink-0"
                      />
                    )}
                    <span>{line.label}</span>
                  </label>
                  <span className="shrink-0 text-right text-xs">
                    {line.ingredientId === null || line.uncertain ? (
                      <em className="text-low">{matchNote(line)}</em>
                    ) : (
                      <span className="text-brand">{matchNote(line)}</span>
                    )}
                  </span>
                </div>

                {/* perché la casella parte vuota: senza questa frase "da
                    confermare" sembra un avviso, non una cosa da fare */}
                {line.uncertain && (
                  <p className="text-xs text-low">
                    Parte escluso, perché l'aggancio è solo un'ipotesi: spunta la casella se è
                    quello giusto.
                  </p>
                )}

                {line.ingredientId === null && line.proposedCategory !== null && (
                  <div className="flex flex-col gap-1">
                    <p className="text-xs text-ink-soft">
                      Non è in anagrafica: lo creo io salvando.
                    </p>
                    <label className="text-xs font-medium text-ink-soft">
                      Categoria
                      <select
                        aria-label={`Categoria per «${line.label}»`}
                        value={line.proposedCategory ?? "altro"}
                        onChange={(e) =>
                          updateLine(line.key, { proposedCategory: e.target.value })
                        }
                        className="mt-1"
                      >
                        {INGREDIENT_CATEGORIES.map((category) => (
                          <option key={category} value={category}>
                            {category}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}

                {/* Stessa condizione di `savable` e della casella di inclusione qui
                    sopra: una riga "da creare salvando" non ha un `ingredientId`
                    ancora, ma è comunque salvabile, e senza questo campo non
                    poteva portare "100 g" — l'unico modo per scriverla era già
                    fissata dalla bozza, non modificabile. */}
                {(line.ingredientId !== null || line.proposedCategory !== null) && (
                  <div className="flex items-end gap-2">
                    <label className="flex-1 text-xs text-ink-soft">
                      Quantità
                      <input
                        aria-label={`Quantità per ${line.label}`}
                        value={line.quantityText}
                        onChange={(e) => updateLine(line.key, { quantityText: e.target.value })}
                        maxLength={QUANTITY_MAX}
                        placeholder="q.b."
                        className="mt-1.5 text-ink"
                      />
                    </label>
                    {line.manual ? (
                      // il ruolo di una riga scelta a mano lo decide chi scrive:
                      // il backend non ha niente da dire su una riga che non ha
                      // proposto lui. Bersagli da pollice, come StatusToggle.
                      <div className="flex gap-1" role="group" aria-label={`Ruolo di ${line.label}`}>
                        {(["primary", "secondary"] as IngredientRole[]).map((role) => (
                          <button
                            key={role}
                            type="button"
                            onClick={() => updateLine(line.key, { role })}
                            aria-pressed={line.role === role}
                            className={`min-h-11 rounded-full px-3 py-2 text-xs font-medium ${
                              line.role === role
                                ? "bg-brand text-white"
                                : "bg-page text-ink-soft"
                            }`}
                          >
                            {ROLE_LABELS[role]}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <span className="pb-2 text-xs text-ink-faint">
                        {ROLE_LABELS[line.role]}
                      </span>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>

          <IngredientPicker
            label="Aggiungi un ingrediente"
            failureNote="Puoi salvare la ricetta comunque, anche senza ingredienti agganciati."
            onPick={attach}
          />
        </div>

        <label className="text-sm">
          Procedimento
          <textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={8}
            className="mt-1.5"
          />
        </label>

        {/* una ricetta senza agganci si salva — è comunque la ricetta che
            l'utente voleva — ma va detto cosa ci rimette, prima del salvataggio
            e non dopo */}
        {savable.length === 0 && (
          <p role="status" className="text-sm text-low">
            Nessun ingrediente agganciato: la ricetta si salva comunque, ma il ricettario non
            potrà dire se puoi cucinarla.
          </p>
        )}

        {/* il motivo sta accanto al pulsante che sta disabilitando: un pulsante
            spento e muto è un vicolo cieco quanto un errore senza spiegazione */}
        {problem && <p className="text-sm text-low">{problem}</p>}

        <button
          type="button"
          onClick={() => save.mutate()}
          disabled={save.isPending || problem !== null}
          className={buttonClasses("primary", "block")}
        >
          {save.isPending ? "Salvo…" : "Salva nel ricettario"}
        </button>

        {/* l'errore sta accanto al pulsante che ha fallito, non in testa allo
            schermo: titolo, procedimento, quantità e spunte restano tutti qui,
            pronti per un altro tentativo */}
        {save.isError && (
          <p role="alert" className="text-sm text-danger">
            {saveProblem(save.error)}
          </p>
        )}
      </div>
    </div>
  );
}
