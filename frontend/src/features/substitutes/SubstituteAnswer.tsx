import { StatusDot } from "../../components/ui/StatusDot";
import { capitalizeFirst } from "../../lib/text";
import type { LineSubstitute, Substitute, SubstitutionVerdict } from "./types";

/** Una risposta di «Sostituisci», da leggere (R5): nel pannello della ricetta, coi
 * pallini della dispensa, e in Anagrafica, senza. Se un sostituto basta lo dice il server
 * (`satisfied`, la stessa regola delle righe): qui si legge, non si giudica. Il nome
 * dentro la frase resta minuscolo; a inizio riga la maiuscola, solo a video. */
export function SubstituteAnswer({
  ingredientName,
  verdict,
  substitutes,
}: {
  ingredientName: string;
  verdict: SubstitutionVerdict;
  substitutes: readonly (Substitute | LineSubstitute)[];
}) {
  if (verdict === "omit") {
    return <p className="text-sm">{`Si può omettere: il piatto riesce anche senza ${ingredientName}.`}</p>;
  }
  if (verdict === "irreplaceable") {
    return <p className="text-sm">{`Insostituibile: senza ${ingredientName} il piatto non si fa.`}</p>;
  }
  return (
    <div>
      <p className="text-sm text-ink-soft">{`Al posto di ${ingredientName}:`}</p>
      <ul>
        {substitutes.map((substitute) => (
          <li key={substitute.ingredient_id} className="flex items-center gap-2 py-1 text-sm">
            {"availability" in substitute && <StatusDot availability={substitute.availability} />}
            <span className="min-w-0">
              <span className="font-medium">{capitalizeFirst(substitute.name)}</span>
              {substitute.note && <span className="text-ink-soft"> · {substitute.note}</span>}
              {"satisfied" in substitute && substitute.satisfied && (
                <span className="ml-2 text-xs font-medium text-brand">ce l'hai</span>
              )}
              {"satisfied" in substitute && !substitute.satisfied && substitute.availability === "low" && (
                <span className="ml-2 text-xs font-medium text-low">non basta</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
