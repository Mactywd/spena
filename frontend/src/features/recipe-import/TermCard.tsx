import { useState } from "react";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Card } from "../../components/ui/Card";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { INGREDIENT_CATEGORIES } from "../../domain/categories";
import type { ImportTerm, TermProposal } from "../../domain/types";

export type Decision = {
  action: "map" | "create" | "ignore";
  ingredient_id?: string;
  name?: string;
  display_name?: string;
  category?: string;
  role_override?: "primary" | "secondary";
};

/** Cosa farà il pulsante, detto in parole.
 *
 * «Collega a pasta» e «Crea Speck in carne» sono frasi che si leggono e si
 * confermano; «Applica proposta» costringerebbe a fidarsi di qualcosa che non si
 * vede, che è esattamente ciò che la revisione esiste per evitare.
 */
function proposalLabel(proposal: TermProposal, term: ImportTerm): string | null {
  if (proposal.action === "map") {
    // Il backend porta il nome canonico con la proposta "map" (vedi TermProposal
    // in terms.py): lo preferiamo sempre. Il fallback sull'aggancio testuale resta
    // solo per una proposta più vecchia o incompleta che ne fosse priva — senza,
    // il pulsante tornerebbe al generico «l'ingrediente» anche quando un nome vero
    // è disponibile altrove.
    const name =
      proposal.name ??
      (term.suggestion?.ingredient_id === proposal.ingredient_id
        ? term.suggestion.name
        : null);
    return `Collega a ${name ?? "l'ingrediente"}`;
  }
  if (proposal.action === "create")
    return `Crea «${proposal.display_name ?? proposal.name}» in ${proposal.category}`;
  return `Ignora «${term.display_name}»`;
}

export function TermCard({
  term,
  proposal,
  proposalsReady,
  suggestionName,
  pending,
  onDecide,
}: {
  term: ImportTerm;
  /** La proposta di Claude, quando è arrivata. */
  proposal: TermProposal | null;
  /** Se il giro di proposte in corso (quando c'è) si è già stabilizzato, riuscito o
   * no. Mentre non lo è, la scorciatoia resta nascosta invece di mostrare subito
   * l'aggancio testuale e poi magari sostituirlo con la proposta vera: un pulsante
   * che cambia risposta da solo è peggio di un attimo senza pulsante. */
  proposalsReady: boolean;
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

  // la proposta di Claude, se c'è; altrimenti l'aggancio testuale, che è sempre
  // meglio di nessun pulsante: un termine senza scorciatoia costa tre tocchi
  const shortcut: TermProposal | null = !proposalsReady
    ? null
    : proposal ??
      (suggestionName !== null && term.suggestion !== null
        ? {
            term_id: term.id, action: "map", ingredient_id: term.suggestion.ingredient_id,
            name: suggestionName, display_name: null, category: null,
          }
        : null);

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

      {/* quando la scorciatoia è "ignora", il pulsante permanente qui sotto fa già
          esattamente questo in un tocco: un secondo pulsante con lo stesso testo
          sarebbe un doppione, non una seconda via. Non è condizionato alla prontezza
          delle proposte (a differenza di `shortcut`): il pulsante permanente resta
          sempre lo stesso elemento, pronto o no che sia la proposta, e non sparisce
          e riappare sotto chi lo sta per toccare. */}
      {shortcut && shortcut.action !== "ignore" && (
        <button
          type="button"
          disabled={pending}
          onClick={() =>
            onDecide(
              shortcut.action === "map"
                ? { action: "map", ingredient_id: shortcut.ingredient_id!, role_override: role }
                : shortcut.action === "create"
                  ? {
                      action: "create", name: shortcut.name!,
                      display_name: shortcut.display_name ?? shortcut.name!,
                      category: shortcut.category!, role_override: role,
                    }
                  : { action: "ignore" }
            )
          }
          className={buttonClasses("primary", "block")}
        >
          {proposalLabel(shortcut, term)}
        </button>
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
        onPick={(ingredient) =>
          onDecide({ action: "map", ingredient_id: ingredient.id, role_override: role })
        }
      />

      {!creating ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => setCreating(true)}
          aria-label={`Crea un ingrediente nuovo per «${term.display_name}»`}
          className={buttonClasses("secondary", "block")}
        >
          Crea un ingrediente nuovo
        </button>
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
          <label className="text-sm font-medium text-ink-soft">
            Categoria
            <select
              aria-label={`Categoria per «${term.display_name}»`}
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="mt-1.5"
            >
              {INGREDIENT_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={pending || newName.trim() === ""}
            onClick={() =>
              onDecide({
                action: "create", name: newName.trim().toLowerCase(),
                display_name: term.display_name, category: newCategory,
                role_override: role,
              })
            }
            className={buttonClasses("primary", "block")}
          >
            Crea e collega
          </button>
        </div>
      )}

      {/* la correzione dell'aglio: un tocco in più, solo per le eccezioni. Il nome
          accessibile porta il termine per lo stesso motivo del picker qui sopra:
          una scheda per termine, e senza il nome la casella è indistinguibile da
          quella della scheda vicina */}
      <label className="flex min-h-11 items-center gap-2.5 text-sm text-ink-soft">
        <input
          type="checkbox"
          aria-label={`Di solito «${term.display_name}» è un ingrediente secondario`}
          checked={alsoSecondary}
          onChange={(e) => setAlsoSecondary(e.target.checked)}
          className="size-5"
        />
        Di solito è secondario
      </label>

      {/* sempre presente, pronta o no che sia la proposta: è la via d'uscita che
          non lascia mai un termine senza decisione possibile. Quando la scorciatoia
          sopra è già "ignora" questo è lo stesso tocco, non un doppione: la
          scorciatoia in quel caso non si renderizza (vedi sopra), quindi qui non
          c'è mai più di un pulsante con questo testo in scheda */}
      <button
        type="button"
        disabled={pending}
        onClick={() => onDecide({ action: "ignore" })}
        className={buttonClasses("ghost", "block")}
      >
        Ignora «{term.display_name}»
      </button>
    </Card>
  );
}
