// L'unico punto da cui l'app prende le icone. Due ragioni: `@tabler/icons-react`
// importato icona per icona pesa solo quel che si usa, e un import sbagliato in un
// posto solo si vede; e la tavola delle azioni della spec T3 §3.3 — quale icona vuol
// dire cosa — resta leggibile qui, invece di spargersi per le schermate.
import type { ComponentType } from "react";

export type IconComponent = ComponentType<{
  size?: number | string;
  stroke?: number | string;
  className?: string;
  "aria-hidden"?: boolean | "true" | "false";
}>;

// ovunque
export {
  IconMenu2,
  IconChevronLeft,
  IconX,
  IconSearch,
  IconPlus,
  IconMinus,
  IconArrowBackUp,
  IconRefresh,
  IconAlertCircle,
  IconEye,
  IconEyeOff,
} from "@tabler/icons-react";
// barra delle schede
export { IconListCheck, IconBox, IconToolsKitchen2 } from "@tabler/icons-react";
// lista e sistemazione
export {
  IconBasketCheck,
  IconClearAll,
  IconBarcode,
  IconListSearch,
  IconScale,
  IconPencilPlus,
  IconReplace,
  IconCalendarPlus,
  IconPackageImport,
} from "@tabler/icons-react";
// dispensa. Il carrello con il + vuol dire «va in lista» ovunque compaia
export { IconShoppingCartPlus, IconCalendarEvent } from "@tabler/icons-react";
// ricette
export {
  IconAdjustmentsHorizontal,
  IconSparkles,
  IconLink,
  IconChefHat,
  IconCircleCheck,
  IconPencil,
  IconTrash,
  IconRestore,
  IconExternalLink,
} from "@tabler/icons-react";
// anagrafica
export {
  IconCursorText,
  IconCategory,
  IconArrowsTransferDown,
  IconArrowsJoin2,
  IconBarcodeOff,
} from "@tabler/icons-react";
// reparti
export {
  IconCarrot,
  IconApple,
  IconMeat,
  IconFish,
  IconCheese,
  IconWheat,
  IconSeedling,
  IconBottle,
  IconPepper,
  IconGlassFull,
  IconCookie,
  IconPackage,
  IconSpray,
  IconBath,
} from "@tabler/icons-react";
