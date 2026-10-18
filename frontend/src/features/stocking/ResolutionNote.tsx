import type { Resolution } from "./stockingView";

/** A cosa si è risolta una confezione, sotto il suo nome, in piccolo: «Sfuso», o il
 * prodotto con la marca — come una riga della dispensa (dal giro: prima si riconosceva
 * solo dal verde). La usano la riga di una voce e quella di una confezione in più. */
export function ResolutionNote({ resolution }: { resolution: Resolution }) {
  return (
    <p className="text-xs text-ink-soft">
      {resolution.kind === "loose" ? (
        "Sfuso"
      ) : (
        <>
          <span>{resolution.product.name}</span>
          {resolution.product.brand && <span> · {resolution.product.brand}</span>}
        </>
      )}
    </p>
  );
}
