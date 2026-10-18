import { useEffect, useRef, useState } from "react";
import { CatalogSearchPanel } from "./CatalogSearchPanel";
import { CustomProductForm, type ProductSuggestion } from "./CustomProductForm";
import { IngredientChooser } from "./IngredientChooser";
import { OffSuggestionQuestion } from "./OffSuggestionQuestion";
import { ScannerPanel } from "./ScannerPanel";
import type { PanelTrigger, Resolution } from "./stockingView";
import { newCodeNote } from "./wording";
import { Button } from "../../components/ui/Button";
import { IconListSearch, IconScale } from "../../components/ui/icons";
import { capitalizeFirst } from "../../lib/text";
import type { Ingredient } from "../../domain/types";

/** L'ingrediente a cui il prodotto si lega. `name` è quello canonico
 * (`Ingredient.name`, in minuscolo): lo stesso che il server manda come
 * `ingredient_name` di una voce o di un prodotto. `kind` `null` vuol dire «non lo so»
 * (un prodotto trovato dal codice non lo porta), e decide solo se il modulo chiede i
 * nutrienti: un detersivo non ha calorie. */
export type ResolverIngredient = {
  id: string;
  name: string;
  kind: "food" | "non_food" | null;
};

type LookedUp = "not_found" | "failed";

/** Il passo aperto: uno alla volta, in un solo stato (T3 Consegna 3). */
type Step =
  | { kind: "scanner" }
  | { kind: "catalog" }
  // il codice nuovo al catalogo che Open Food Facts conosce, per un ingrediente già
  // noto: prima del modulo, la domanda (S20)
  | { kind: "off-question"; barcode: string; suggestion: ProductSuggestion }
  // il codice nuovo nella scansione dalla Dispensa (S3): prima di tutto, di che
  // ingrediente è
  | { kind: "ingredient"; barcode: string; suggestion: ProductSuggestion | null; lookedUp?: LookedUp }
  | {
      kind: "product-form";
      /** Chi l'ha aperto: lì torna il fuoco, annullando. */
      trigger: PanelTrigger;
      barcode: string;
      suggestion: ProductSuggestion | null;
      lookedUp?: LookedUp;
    };

type IngredientStep = Extract<Step, { kind: "ingredient" }>;

/** Il pulsante che aveva aperto il passo, per chi deve rimettergli il fuoco. */
function triggerOf(step: Step): PanelTrigger {
  if (step.kind === "catalog") return "catalog";
  if (step.kind === "product-form") return step.trigger;
  return "scanner";
}

/**
 * La regia dei pannelli che legano una confezione a un prodotto (S3): il codice a
 * barre, il catalogo, la domanda di Open Food Facts, il modulo del prodotto nuovo.
 * Estratta da `StockingScreen`, che la usa per ogni confezione di una voce; la usa anche
 * la Dispensa, per l'ingresso diretto. Una copia sola, perché è qui che stanno le
 * guardie che la prima lezione di `CLAUDE.md` dice di non duplicare:
 *
 * - **l'esito tardivo**: le mutazioni dei pannelli (il lookup del codice, la creazione
 *   del prodotto) chiamano i loro `on…` anche a pannello chiuso o smontato — react-query
 *   li tiene — e con la chiusura di un render passato. Un esito vale solo se il suo passo
 *   è ancora quello aperto (lo stesso oggetto: riaperto è un altro) e il resolver è
 *   ancora montato. Dopo «Annulla», o con un'altra voce davanti, non sceglie niente;
 * - **il codice che segue (S8)**: il codice letto e rimasto senza prodotto — ignoto al
 *   catalogo, o lookup fallito — segue il catalogo e il modulo, da qualunque passo ci si
 *   arrivi. Lo tiene chi usa il resolver (`rememberedCode`), perché deve sopravvivere al
 *   pannello che si chiude; quando seguirlo lo decide solo questo file. Lo sfuso non lo
 *   legge: non c'è un prodotto a cui darlo;
 * - **la `key` del modulo**: un modulo riusato per un altro codice terrebbe i campi di
 *   prima, e salverebbe il prodotto sbagliato in silenzio.
 *
 * Due modi. **Con l'ingrediente** (una voce di «Sistema la spesa», il + della Dispensa)
 * la guardia del 409 è accesa nello scanner, un codice nuovo noto a Open Food Facts passa
 * dalla domanda «È un …?», e annullare chiude. **Senza** (la scansione dalla Dispensa) il
 * prodotto trovato porta il suo ingrediente; un codice nuovo chiede prima di che
 * ingrediente è (`IngredientChooser`, che può crearlo), poi il modulo senza domanda —
 * l'ingrediente l'ha appena detto chi legge —; dal modulo si esce anche sfusi o dal
 * catalogo; e annullare un passo dopo lo scanner torna allo scanner, perché c'è una
 * confezione in mano.
 */
export function ProductResolver({
  label,
  ingredient,
  start,
  rememberedCode,
  onRememberCode,
  onResolved,
  onStep,
  onCancel,
}: {
  /** Di che cosa, nei titoli dei pannelli. `null`: la scansione dalla Dispensa, che
   * parte senza; dopo la scelta dell'ingrediente i titoli dicono il suo nome. */
  label: string | null;
  /** L'ingrediente atteso; `null` solo con `start` "scanner". */
  ingredient: ResolverIngredient | null;
  start: "scanner" | "catalog";
  rememberedCode: string | undefined;
  onRememberCode: (code: string | null) => void;
  onResolved: (resolution: Resolution, ingredient: ResolverIngredient) => void;
  /** Un passo nuovo è comparso al posto di un altro: il pulsante che aveva il fuoco è
   * sparito, e chi ospita il resolver sa dove rimetterlo. */
  onStep?: (trigger: PanelTrigger) => void;
  onCancel: (trigger: PanelTrigger) => void;
}) {
  const [first] = useState<Step>(() =>
    start === "scanner" ? { kind: "scanner" } : { kind: "catalog" }
  );
  const [step, setStep] = useState<Step>(first);
  // Il passo aperto adesso, per chi arriva in ritardo (vedi sopra): un ref e non lo
  // stato, perché l'esito tardivo legge la chiusura di un render passato
  const current = useRef<Step | null>(first);
  const alive = useRef(false);
  // l'ingrediente scelto nel passo «Di che ingrediente è?», senza ingrediente atteso
  const [chosen, setChosen] = useState<ResolverIngredient | null>(null);
  // ogni ritorno allo scanner lo fa rinascere: la fotocamera si rilascia al primo codice
  // letto (`BarcodeScanner`), e chi torna a leggere ne vuole una accesa e un campo vuoto
  const [scannerRound, setScannerRound] = useState(0);
  const target = ingredient ?? chosen;

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  function isOpen(which: Step): boolean {
    return alive.current && current.current === which;
  }

  function show(next: Step) {
    current.current = next;
    setStep(next);
    onStep?.(triggerOf(next));
  }

  function backToScanner() {
    setChosen(null);
    // il codice di prima è di una confezione scartata: non segue la prossima
    onRememberCode(null);
    setScannerRound((round) => round + 1);
    show({ kind: "scanner" });
  }

  /** Chiude senza scegliere. Senza ingrediente atteso, un passo dopo lo scanner torna a
   * leggere; lo scanner stesso, e ogni passo con l'ingrediente, chiudono. */
  function close(which: Step) {
    if (!isOpen(which)) return;
    if (ingredient === null && which.kind !== "scanner") {
      backToScanner();
      return;
    }
    current.current = null;
    onCancel(triggerOf(which));
  }

  /** La scelta arrivata da un passo: vale solo se quel passo è ancora aperto. */
  function resolveFrom(which: Step, resolution: Resolution, of: ResolverIngredient) {
    if (!isOpen(which)) return;
    current.current = null;
    onResolved(resolution, of);
  }

  /** Un codice nuovo al catalogo, che si è deciso di usare: senza ingrediente, prima
   * l'ingrediente; con, se Open Food Facts lo conosce si chiede se è lui, se no il
   * modulo. Il codice da qui segue il catalogo e il modulo (S8). */
  function proceedWithNewCode(which: Step, code: string, suggestion: ProductSuggestion | null) {
    if (!isOpen(which)) return;
    onRememberCode(code);
    if (target === null) {
      show({
        kind: "ingredient",
        barcode: code,
        suggestion,
        lookedUp: suggestion ? undefined : "not_found",
      });
      return;
    }
    show(
      suggestion
        ? { kind: "off-question", barcode: code, suggestion }
        : {
            kind: "product-form",
            trigger: "scanner",
            barcode: code,
            suggestion: null,
            lookedUp: "not_found",
          }
    );
  }

  /** «Crea il prodotto a mano», dallo scanner o dal catalogo. Il codice letto prima
   * segue anche questa uscita (S8), da qualunque passo si arrivi. */
  function openProductForm(trigger: PanelTrigger, barcode: string, lookedUp?: "failed") {
    const code = barcode || rememberedCode || "";
    if (target === null) {
      show({ kind: "ingredient", barcode: code, suggestion: null, lookedUp });
      return;
    }
    show({ kind: "product-form", trigger, barcode: code, suggestion: null, lookedUp });
  }

  function chooseIngredient(which: IngredientStep, picked: Ingredient) {
    if (!isOpen(which)) return;
    setChosen({ id: picked.id, name: picked.name, kind: picked.kind });
    show({
      kind: "product-form",
      trigger: "scanner",
      barcode: which.barcode,
      suggestion: which.suggestion,
      lookedUp: which.lookedUp,
    });
  }

  if (step.kind === "scanner") {
    return (
      <ScannerPanel
        key={scannerRound}
        label={label}
        ingredientId={ingredient?.id ?? null}
        onProduct={(product) =>
          resolveFrom(
            step,
            { kind: "product", product },
            // senza ingrediente atteso, entra quello del prodotto: lo dice il server
            ingredient ?? { id: product.ingredient_id, name: product.ingredient_name, kind: null }
          )
        }
        onNewCode={(code, suggestion) => proceedWithNewCode(step, code, suggestion)}
        onUnlinkedCode={onRememberCode}
        onCreateByHand={(code, lookedUp) => openProductForm("scanner", code, lookedUp)}
        onCancel={() => close(step)}
      />
    );
  }

  if (step.kind === "ingredient") {
    return (
      <div className="flex flex-col gap-3 rounded-card border border-line p-3">
        <h2 className="font-semibold">Di che ingrediente è?</h2>
        {/* nome e marca di Open Food Facts, o cosa si sa del codice: perché si sappia di
            cosa si sta parlando. Il campo parte vuoto: il nome di un prodotto non deve
            diventare il nome di un ingrediente */}
        <p className="text-sm text-ink">{newCodeNote(step.barcode, step.suggestion, step.lookedUp)}</p>
        <IngredientChooser
          label="Ingrediente"
          failureNote="Puoi comunque aggiungerlo."
          initialTerm=""
          onChosen={(picked) => chooseIngredient(step, picked)}
          after={
            <Button variant="ghost" onClick={() => close(step)} className="self-start">
              Annulla
            </Button>
          }
        />
      </div>
    );
  }

  // ogni altro passo lega un prodotto a un ingrediente: senza, niente da mostrare (non
  // succede: senza ingrediente atteso ci si arriva solo dopo averlo scelto)
  if (target === null) return null;
  const targetLabel = label ?? capitalizeFirst(target.name);

  if (step.kind === "catalog") {
    return (
      <CatalogSearchPanel
        itemLabel={targetLabel}
        ingredientId={target.id}
        // il codice letto un attimo prima segue anche questa uscita (S8): senza, la
        // prossima scansione dello stesso codice non trovava niente
        onPicked={(product) =>
          resolveFrom(step, { kind: "product", product, barcode: rememberedCode }, target)
        }
        onCreateByHand={() => openProductForm("catalog", "")}
        onCancel={() => close(step)}
      />
    );
  }

  if (step.kind === "off-question") {
    return (
      <OffSuggestionQuestion
        ingredientName={target.name}
        suggestion={step.suggestion}
        onYes={() =>
          show({
            kind: "product-form",
            trigger: "scanner",
            barcode: step.barcode,
            suggestion: step.suggestion,
          })
        }
        onNo={() => {
          // indietro a prima del codice. Il codice non segue — è di un'altra cosa, e dal
          // catalogo finirebbe al prodotto sbagliato
          onRememberCode(null);
          close(step);
        }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="rounded-card border border-line">
        <CustomProductForm
          // senza key React riusa l'istanza passando da un codice all'altro: i campi
          // restano quelli di prima mentre il codice è già il nuovo, e si salva il
          // prodotto sbagliato, in silenzio. Fra due bersagli diversi rinasce il resolver
          key={step.barcode}
          ingredientId={target.id}
          itemLabel={targetLabel}
          barcode={step.barcode}
          suggestion={step.suggestion}
          lookedUp={step.lookedUp}
          isNonFood={target.kind === "non_food"}
          onCreated={(product) => resolveFrom(step, { kind: "product", product }, target)}
          onCancel={() => close(step)}
        />
      </div>
      {/* Senza ingrediente atteso non ci sono le icone di una voce sotto cui tornare:
          le altre due strade stanno qui. Lo sfuso è «mai un vicolo cieco» (bozza §4.2);
          il catalogo trova il prodotto che c'è già senza codice, e il codice lo segue
          (S8) — B, deciso da Mattia il 2026-10-09 */}
      {ingredient === null && (
        <div className="flex flex-wrap gap-2">
          <Button icon={IconListSearch} onClick={() => show({ kind: "catalog" })}>
            Cerca a catalogo
          </Button>
          <Button icon={IconScale} onClick={() => resolveFrom(step, { kind: "loose" }, target)}>
            Sfuso, senza marca
          </Button>
        </div>
      )}
    </div>
  );
}
