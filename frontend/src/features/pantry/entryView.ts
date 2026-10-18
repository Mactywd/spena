import type { ResolverIngredient } from "../stocking/ProductResolver";
import type { Product } from "../../domain/types";
import { capitalizeFirst } from "../../lib/text";

/** L'ingrediente di una confezione che entra dalla Dispensa: quello scelto o creato col
 * +, o quello del prodotto letto dal codice (S3). */
export type EntryIngredient = ResolverIngredient;

/** Cosa sta per entrare: un ingrediente, e un prodotto o niente (sfuso). `barcode` è il
 * codice letto prima di scegliere il prodotto a catalogo (S8): se darlo al prodotto lo
 * decide il backend. */
export type EntryChoice = { ingredient: EntryIngredient; product: Product | null; barcode?: string };

/** Il titolo della scheda, e il nome nei nomi dei suoi pulsanti: il prodotto col suo
 * nome, o l'ingrediente sfuso con la maiuscola (solo a video, spec T3 §4.7). */
export function entryTitle(choice: EntryChoice): string {
  return choice.product ? choice.product.name : capitalizeFirst(choice.ingredient.name);
}

/** Quel che dice l'avviso «In dispensa: …»: la marca davanti al nome, come si legge
 * sulla confezione («Fage Total 0%»). */
export function entryLabel(choice: EntryChoice): string {
  const { product } = choice;
  if (!product) return capitalizeFirst(choice.ingredient.name);
  return product.brand ? `${product.brand} ${product.name}` : product.name;
}
