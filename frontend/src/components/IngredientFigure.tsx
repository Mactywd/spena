import { departmentStyle } from "./ui/departments";

/** La figura di un ingrediente (S12, bozza §3.A): la sua emoji su un quadratino da 28 px,
 * o, dove non ce l'ha, l'icona del suo reparto in `ink-faint`. Monocroma e senza la tinta
 * del reparto: le tinte stanno solo nel titolo della sezione (spec T3 §3.3), e su una
 * riga si confonderebbero coi colori degli stati.
 *
 * Il fondo `page` sul `card` della sezione sta a 1,11:1 di proposito: è un appoggio, non
 * un bordo che dice qualcosa. Il ripiego sta sopra 3:1 sul suo fondo (`theme.test.ts`,
 * misurato anche nel browser da `e2e/style.spec.ts`).
 *
 * `aria-hidden`: il nome è già scritto accanto, e «formaggio Mozzarella» letto a voce
 * è rumore. `data-figure` dice quale delle due si vede, per le prove.
 *
 * Sta in `components/` e non in `features/pantry/` perché la usa anche l'Anagrafica,
 * dove la figura si corregge. */
export function IngredientFigure({
  emoji,
  category,
  className = "",
}: {
  emoji: string | null | undefined;
  category: string | null;
  className?: string;
}) {
  const { icon: Icon } = departmentStyle(category);
  return (
    <span
      aria-hidden="true"
      data-figure={emoji ? "emoji" : "reparto"}
      className={`flex size-7 shrink-0 items-center justify-center rounded-lg bg-page text-ink-faint ${className}`}
    >
      {emoji ? (
        <span className="text-lg leading-none">{emoji}</span>
      ) : (
        <Icon className="size-4.5" stroke={1.8} />
      )}
    </span>
  );
}
