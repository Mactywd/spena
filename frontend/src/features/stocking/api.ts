import { apiFetch } from "../../api/client";
import type { BarcodeLookup, Product } from "../../domain/types";

// Cerca per codice e basta: `find_by_barcode` non filtra per ingrediente, quindi la
// referenza che torna può essere di un altro ingrediente. Confrontarla con
// l'ingrediente della voce è compito del chiamante — la dispensa respinge quella
// coppia con 409, e la sistemazione è tutto-o-niente (vedi lookup.onSuccess in
// StockingScreen).
export function lookupBarcode(code: string) {
  return apiFetch<BarcodeLookup>(`/products/barcode/${encodeURIComponent(code)}`);
}

// La seconda delle tre strade della spec §8.2: la usa CatalogSearchPanel per
// riagganciare un prodotto già in catalogo senza passare dal codice a barre, che non
// si legge se la confezione è aperta, il codice è rovinato o la fotocamera non c'è.
// Cerca su nome e marca (app/repositories/products.py) e non filtra per ingrediente:
// è il chiamante a doverlo fare, e il perché sta nel JSDoc di `ingredientId`.
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
