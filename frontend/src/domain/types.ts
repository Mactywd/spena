// Rispecchiano gli schemi Pydantic del backend. La logica resta là: qui solo forme.
export type PantryStatus = "available" | "low" | "finished";
export type Availability = "available" | "low" | "missing";
export type IngredientRole = "primary" | "secondary";
export type RecipeSource = "dataset" | "manual" | "ai";

export interface Ingredient {
  id: string;
  name: string;
  display_name: string;
  category: string;
}

export interface Product {
  id: string;
  ingredient_id: string;
  name: string;
  brand: string | null;
  barcode: string | null;
  source: string;
  nutrients: Record<string, number> | null;
  image_url: string | null;
}

export interface BarcodeLookup {
  found: boolean;
  origin: "catalog" | "openfoodfacts" | "unknown";
  product: Product | null;
  suggestion: {
    name: string;
    brand: string | null;
    barcode: string;
    nutrients: Record<string, number>;
    image_url: string | null;
  } | null;
}

export interface PantryItem {
  id: string;
  ingredient_id: string;
  product_id: string | null;
  ingredient_name: string;
  ingredient_category: string;
  product_name: string | null;
  product_brand: string | null;
  status: PantryStatus;
  note: string | null;
  added_at: string;
}

export interface ShoppingItem {
  id: string;
  raw_text: string;
  ingredient_id: string | null;
  ingredient_name: string | null;
  ingredient_category: string | null;
  status: "pending" | "checked" | "done" | "archived";
  reason: "manual" | "finished_while_cooking" | "low_while_cooking";
  created_at: string;
}

export interface RecipeSummary {
  id: string;
  title: string;
  description: string | null;
  source: RecipeSource;
  missing: number;
  cookable: boolean;
}

export interface RecipeIngredientLine {
  ingredient_id: string;
  ingredient_name: string;
  role: IngredientRole;
  quantity_text: string | null;
  note: string | null;
  availability: Availability;
  satisfied: boolean;
}

export interface RecipeDetail extends RecipeSummary {
  instructions: string;
  servings: number | null;
  source_ref: string | null;
  ingredients: RecipeIngredientLine[];
}
