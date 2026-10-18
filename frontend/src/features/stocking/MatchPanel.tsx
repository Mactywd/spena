import { IngredientChooser } from "./IngredientChooser";
import { Button } from "../../components/ui/Button";
import type { Ingredient, ShoppingItem } from "../../domain/types";

/**
 * «Abbina», sotto una voce spuntata senza ingrediente (spec T3 §4.3): il testo libero
 * della lista non ha mai trovato un corrispondente, e la voce non può sparire in
 * silenzio dal conto finale. Si sceglie un ingrediente dal selettore unico, oppure lo si
 * crea: la scelta e la creazione (S6, S19) stanno in `IngredientChooser`, che usano
 * anche «Articolo aggiuntivo» e la Dispensa (S3).
 */
export function MatchPanel({
  item,
  onMatched,
  onCancel,
}: {
  item: ShoppingItem;
  onMatched: (ingredient: Ingredient) => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-card border border-line p-3">
      <h2 className="font-semibold">Abbina «{item.raw_text}»</h2>
      <IngredientChooser
        label="Abbina un ingrediente"
        accessibleLabel={`Abbina un ingrediente per ${item.raw_text}`}
        failureNote="Puoi comunque aggiungerlo."
        initialTerm={item.raw_text}
        onChosen={onMatched}
        before={
          <p className="text-sm text-ink-soft">
            Scegli a quale ingrediente corrisponde: senza, non entra in dispensa.
          </p>
        }
        after={
          <Button variant="ghost" onClick={onCancel} className="self-start">
            Annulla
          </Button>
        }
      />
    </div>
  );
}
