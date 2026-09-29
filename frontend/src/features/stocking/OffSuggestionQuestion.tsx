import { Button } from "../../components/ui/Button";
import type { ProductSuggestion } from "./CustomProductForm";

/** Il nome di Open Food Facts accanto alla domanda, in una frase sola. */
function describeSuggestion(suggestion: ProductSuggestion): string {
  const what = suggestion.name ? `«${suggestion.name}»` : "senza nome";
  const by = suggestion.brand ? `, di ${suggestion.brand}` : "";
  return `Su Open Food Facts è ${what}${by}.`;
}

/**
 * La domanda prima del modulo, quando un codice nuovo al catalogo è noto a Open
 * Food Facts (S20). Il modulo precompilato si apriva direttamente per
 * l'ingrediente della voce, con «Salva» pieno: gli spaghetti letti sulla voce
 * «pomodoro» diventavano per sempre un prodotto di pomodoro, e le ricette al
 * pomodoro cucinabili con la pasta. La domanda si fa sempre, senza confrontare i
 * nomi: «Spaghetti n.5» e «pomodoro» non si somigliano, ma nemmeno «Passata
 * Rustica» e «passata di pomodoro» in modo affidabile, e un confronto che a volte
 * tace è peggio di una domanda che costa un tocco.
 */
export function OffSuggestionQuestion({
  ingredientName,
  suggestion,
  onYes,
  onNo,
}: {
  ingredientName: string;
  suggestion: ProductSuggestion;
  onYes: () => void;
  onNo: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-card border border-line p-3">
      <h2 className="font-semibold">È un «{ingredientName}»?</h2>
      <p className="text-ink">{describeSuggestion(suggestion)}</p>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={onYes}>
          Sì
        </Button>
        <Button onClick={onNo}>No, è un'altra cosa</Button>
      </div>
    </div>
  );
}
