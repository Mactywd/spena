import { Button } from "../../components/ui/Button";
import { WORLDS, WORLD_LABELS, type PantryWorld } from "./pantryView";

/** «Tutto / Cibo / Casa» (S14): tre pulsanti a larghezza uguale, uno solo premuto.
 * Pulsanti con `aria-pressed` e non radio, come vuole la bozza: un controllo scelto. Il
 * premuto è `primary` e gli altri `secondary`, la forma del gradino scelto di «Cosa posso
 * cucinare» (`MissingBudgetFilter`), l'unico altro posto dell'app dove si sceglie uno fra
 * pochi: l'ambra del riepilogo delle scadenze direbbe «scade», che qui non c'entra.
 * Deciso da Claude su delega di Mattia. Ritoccare quello premuto non cambia niente. */
export function WorldSelector({
  value,
  onChange,
}: {
  value: PantryWorld;
  onChange: (world: PantryWorld) => void;
}) {
  return (
    <div role="group" aria-label="Cosa mostrare" className="flex gap-2">
      {WORLDS.map((world) => (
        <Button
          key={world}
          variant={world === value ? "primary" : "secondary"}
          aria-pressed={world === value}
          onClick={() => onChange(world)}
          className="flex-1"
        >
          {WORLD_LABELS[world]}
        </Button>
      ))}
    </div>
  );
}
