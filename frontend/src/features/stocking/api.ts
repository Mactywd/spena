import { apiFetch } from "../../api/client";
import type { BarcodeLookup, Product } from "../../domain/types";

export function lookupBarcode(code: string) {
  return apiFetch<BarcodeLookup>(`/products/barcode/${encodeURIComponent(code)}`);
}

export function searchProducts(query: string) {
  return apiFetch<Product[]>(`/products/search?q=${encodeURIComponent(query)}`);
}

export function createProduct(body: {
  ingredient_id: string;
  name: string;
  brand?: string;
  barcode?: string;
  nutrients?: Record<string, number>;
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
