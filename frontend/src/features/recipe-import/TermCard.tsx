import { useState } from "react";
import { CategorySelect } from "../../components/CategorySelect";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Checkbox } from "../../components/ui/Checkbox";
import type { ImportTerm } from "../../domain/types";
import { withPrepositionA } from "../../lib/text";

export type Decision = {
  action: "map" | "create" | "ignore";
  ingredient_id?: string;
  name?: string;
  display_name?: string;
  category?: string;
  role_override?: "primary" | "secondary";
};

export function TermCard({
  term,
  suggestionName,
  pending,
  onDecide,
}: {
  term: ImportTerm;
  /** Il nome dell'aggancio testuale: è la proposta di riserva, e c'è anche senza AI. */
  suggestionName: string | null;
  pending: boolean;
  onDecide: (decision: Decision) => void;
}) {
  const [alsoSecondary, setAlsoSecondary] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState(term.display_name.toLowerCase());
  const [newCategory, setNewCategory] = useState<string>("altro");

  const role = alsoSecondary ? ("secondary" as const) : undefined;

  // l'aggancio testuale, che è sempre meglio di nessun pulsante: un termine senza
  // scorciatoia costa tre tocchi. Non ci sono più proposte dell'AI da confermare
  // qui: quelle si rivedono, già applicate, dall'elenco «Decisioni recenti».
  const shortcut: { ingredient_id: string; name: string } | null =
    suggestionName !== null && term.suggestion !== null
      ? { ingredient_id: term.suggestion.ingredient_id, name: suggestionName }
      : null;

  // L'aggancio testuale eredita `certain` da `match_name`
  // (backend/app/services/ingredient_match.py): certo è una coincidenza esatta su
  // nome o alias, un fatto che non ha bisogno di conferma; incerto è il risultato
  // migliore di una ricerca per somiglianza, un'ipotesi come tante altre. Questo è
  // il difetto critico: "Pinoli" diventava alias permanente di "pisello" con un
  // tocco sul pulsante primario, perché qui `certain` non veniva mai letto.
  const shortcutIsCertain = shortcut !== null && term.suggestion?.certain === true;

  // In volo ogni pulsante della scheda è `busy` e non `disabled`: il fuoco resta dov'è
  // (regola di T3). «Crea e collega» senza nome è «non ancora», col perché sotto.
  return (
    <Card as="li" className="flex flex-col gap-3">
      <div>
        <p className="font-medium">{term.display_name}</p>
        <p className="text-xs text-ink-faint">
          {term.occurrences === 1 ? "1 ricetta in attesa" : `${term.occurrences} ricette in attesa`}
        </p>
        {term.waiting_titles.length > 0 && (
          // i titoli non sono decorazione: «Scorza di limone» si giudica
          // diversamente in una torta e in un arrosto
          <p className="pt-1 text-xs text-ink-soft">{term.waiting_titles.join(" · ")}</p>
        )}
      </div>

      {shortcut && shortcutIsCertain && (
        <Button
          variant="primary"
          shape="block"
          busy={pending}
          onClick={() =>
            onDecide({ action: "map", ingredient_id: shortcut.ingredient_id, role_override: role })
          }
        >
          {`Collega ${withPrepositionA(shortcut.name)}`}
        </Button>
      )}

      {/* il nome accessibile porta il termine: la schermata mette una scheda per
          ogni termine in attesa, e senza il nome qui dentro uno screen reader
          sente N controlli identici — "Collega a un altro ingrediente" non dice a
          chi lo ascolta quale dei tanti termini stia per agganciare */}
      <IngredientPicker
        label="Collega a un altro ingrediente"
        accessibleLabel={`Collega «${term.display_name}» a un altro ingrediente`}
        failureNote="Puoi crearne uno nuovo qui sotto, o ignorare il termine."
        disabled={pending}
        kind="food"
        onPick={(ingredient) =>
          onDecide({ action: "map", ingredient_id: ingredient.id, role_override: role })
        }
      />

      {!creating ? (
        <Button
          shape="block"
          busy={pending}
          onClick={() => setCreating(true)}
          accessibleName={`Crea un ingrediente nuovo per «${term.display_name}»`}
        >
          Crea un ingrediente nuovo
        </Button>
      ) : (
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-ink-soft">
            Nome dell'ingrediente
            <input
              aria-label={`Nome dell'ingrediente per «${term.display_name}»`}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mt-1.5"
            />
          </label>
          {/* solo i reparti del cibo: il termine viene da una ricetta, e una ricetta non
              può nominare un non alimentare */}
          <CategorySelect
            value={newCategory}
            onChange={setNewCategory}
            foodOnly
            accessibleLabel={`Reparto per «${term.display_name}»`}
          />
          <Button
            variant="primary"
            shape="block"
            busy={pending}
            unavailableReason={newName.trim() === "" ? "Scrivi il nome per crearlo." : undefined}
            onClick={() =>
              onDecide({
                action: "create", name: newName.trim().toLowerCase(),
                display_name: term.display_name, category: newCategory,
                role_override: role,
              })
            }
          >
            Crea e collega
          </Button>
        </div>
      )}

      {/* l'aggancio testuale incerto: una somiglianza di nome, non un fatto verificato
          (vedi `shortcutIsCertain` sopra). Sta sotto ai controlli a mano, e ha la misura
          del resto della scheda — un `ghost` in `text-sm`, non a tutta larghezza (dal
          giro: «è enorme anche quando è assurdo», «Aragosta» → «lonza di maiale»). Non lo
          togliamo — un termine senza scorciatoia costa tre tocchi — lo retrocediamo. */}
      {shortcut && !shortcutIsCertain && (
        <div className="flex flex-col items-start gap-1">
          <Button
            variant="ghost"
            busy={pending}
            onClick={() =>
              onDecide({ action: "map", ingredient_id: shortcut.ingredient_id, role_override: role })
            }
          >
            {`Forse «${shortcut.name}» — tocca per confermare`}
          </Button>
          <p className="text-xs text-ink-faint">
            È solo una somiglianza tra i nomi: verificala prima di confermarla, oppure scegli
            un altro ingrediente con i controlli qui sopra.
          </p>
        </div>
      )}

      {/* la correzione dell'aglio: un tocco in più, solo per le eccezioni. Il nome
          accessibile porta il termine per lo stesso motivo del picker qui sopra: una
          scheda per termine. Il bersaglio è il quadrato da 44 px di `Checkbox` */}
      <label className="flex min-h-11 items-center gap-1 text-sm text-ink-soft">
        <Checkbox
          aria-label={`Di solito «${term.display_name}» è un ingrediente secondario`}
          checked={alsoSecondary}
          onChange={(e) => setAlsoSecondary(e.target.checked)}
        />
        Di solito è secondario
      </label>

      {/* sempre presente: è la via d'uscita che non lascia mai un termine senza
          decisione possibile. Quando la scorciatoia sopra è già certa questo resta
          comunque un pulsante distinto, perché la scorciatoia certa collega, non
          ignora: non c'è mai un doppione con lo stesso testo in scheda */}
      <Button
        variant="ghost"
        shape="block"
        busy={pending}
        onClick={() => onDecide({ action: "ignore" })}
      >
        {`Ignora «${term.display_name}»`}
      </Button>
    </Card>
  );
}
