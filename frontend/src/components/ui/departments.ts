import {
  IconApple,
  IconBath,
  IconBottle,
  IconCarrot,
  IconCheese,
  IconCookie,
  IconFish,
  IconGlassFull,
  IconMeat,
  IconPackage,
  IconPepper,
  IconSeedling,
  IconSpray,
  IconWheat,
  type IconComponent,
} from "./icons";

export type DepartmentTint = "peach" | "pink" | "blue" | "sand" | "slate";

// Le classi per intero, non costruite con `bg-dept-${tint}`: Tailwind trova le classi
// leggendo il sorgente, e una classe composta a runtime non la genera mai.
export const TINT_CLASSES: Record<DepartmentTint, string> = {
  peach: "bg-dept-peach text-dept-peach-ink",
  pink: "bg-dept-pink text-dept-pink-ink",
  blue: "bg-dept-blue text-dept-blue-ink",
  sand: "bg-dept-sand text-dept-sand-ink",
  slate: "bg-dept-slate text-dept-slate-ink",
};

// Spec T3 §3.3. Cinque tinte per famiglia, non quattordici colori: quattordici non si
// imparano, e finirebbero addosso ai colori degli stati.
const DEPARTMENTS: Record<string, { icon: IconComponent; tint: DepartmentTint }> = {
  verdura: { icon: IconCarrot, tint: "peach" },
  frutta: { icon: IconApple, tint: "peach" },
  carne: { icon: IconMeat, tint: "pink" },
  dolci: { icon: IconCookie, tint: "pink" },
  pesce: { icon: IconFish, tint: "blue" },
  latticini: { icon: IconCheese, tint: "blue" },
  bevande: { icon: IconGlassFull, tint: "blue" },
  cereali: { icon: IconWheat, tint: "sand" },
  // Tabler non ha un fagiolo: il germoglio è il ripiego più vicino (spec §3.3)
  legumi: { icon: IconSeedling, tint: "sand" },
  condimenti: { icon: IconBottle, tint: "sand" },
  spezie: { icon: IconPepper, tint: "sand" },
  altro: { icon: IconPackage, tint: "slate" },
  casa: { icon: IconSpray, tint: "slate" },
  igiene: { icon: IconBath, tint: "slate" },
};

const UNKNOWN = { icon: IconPackage, tint: "slate" as const };

/** Icona e tinta di un reparto. `null` è «Senza reparto», la sezione delle voci
 * libere della lista: stessa veste di «altro», perché è lo stesso non-sapere. */
export function departmentStyle(category: string | null): { icon: IconComponent; tint: DepartmentTint } {
  return (category && DEPARTMENTS[category]) || UNKNOWN;
}
