import { apiFetch } from "../../api/client";
import type { BarcodeLookup, Product } from "../../domain/types";

export function lookupBarcode(code: string) {
  return apiFetch<BarcodeLookup>(`/products/barcode/${encodeURIComponent(code)}`);
}

// Richiesta dall'interfaccia del brief e non ancora consumata: la ricerca per
// nome del catalogo è la strada di Task 20 (dispensa), dove si aggancia un
// prodotto già noto senza passare dal codice a barre.
export function searchProducts(query: string) {
  return apiFetch<Product[]>(`/products/search?q=${encodeURIComponent(query)}`);
}

export function createProduct(body: {
  ingredient_id: string;
  name: string;
  brand?: string;
  barcode?: string;
  nutrients?: Record<string, number>;
  // la conferma di un suggerimento è l'unico momento in cui provenienza e
  // immagine esistono: non riportarle qui significa perderle per sempre
  // (docstring di ProductCreate, backend/app/schemas/product.py)
  source?: "openfoodfacts" | "custom";
  image_url?: string;
}) {
  return apiFetch<Product>("/products", { method: "POST", body: JSON.stringify(body) });
}

export function stockItems(
  entries: { shopping_item_id: string; ingredient_id: string; product_id: string | null }[]
) {
  return apiFetch<{ created: number }>("/shopping-list/stock", {
    method: "POST",
    body: JSON.stringify({ entries }),
  });
}
