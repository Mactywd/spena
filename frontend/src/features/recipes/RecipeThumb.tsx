import { RecipeImage } from "./RecipeImage";
import { departmentStyle, TINT_CLASSES } from "../../components/ui/departments";
import { IconToolsKitchen2 } from "../../components/ui/icons";

/** La miniatura di una riga del ricettario, 56 px (spec T3 §4.5).
 *
 * Sotto c'è sempre l'icona del reparto principale della ricetta sulla sua tinta — il
 * reparto lo decide il server, `main_department` — e sopra, se c'è, la foto. Così mentre
 * la foto carica, o se non carica, si vede l'icona: mai un rettangolo bianco (dal giro:
 * «mentre la foto carica mostrano un rettangolo bianco»). Senza reparto, l'icona del
 * ricettario su ardesia: «altro» è un pacco, e una ricetta non è un pacco.
 *
 * Tutta decorativa (`aria-hidden`, `alt=""`): il titolo è già il nome del collegamento,
 * e l'alt della foto lo farebbe leggere due volte. */
export function RecipeThumb({
  imageUrl,
  department,
}: {
  imageUrl: string | null;
  department: string | null;
}) {
  const { icon: Icon, tint } = department
    ? departmentStyle(department)
    : { icon: IconToolsKitchen2, tint: "slate" as const };
  return (
    <span
      data-recipe-thumb
      data-dept={department ?? ""}
      aria-hidden="true"
      className={`relative flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-xl ${TINT_CLASSES[tint]}`}
    >
      <Icon className="size-6" stroke={1.8} />
      <RecipeImage url={imageUrl} alt="" className="absolute inset-0 size-full object-cover" />
    </span>
  );
}
