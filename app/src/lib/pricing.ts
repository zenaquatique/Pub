// Estimation du coût des recettes et des articles de la liste de courses.
//
// Limite connue (V1) : TheMealDB ne fournit pas de quantités standardisées
// ("1 cup", "a pinch", "200g" mélangés), donc on ne peut pas calculer un
// prix exact. On applique une heuristique simple : chaque ingrédient
// reconnu dans `ingredient_price_estimates` (alimenté quotidiennement par
// Open Prices, voir supabase/functions/refresh-prices) compte pour une
// fraction FIXE de son prix unitaire de référence ; un ingrédient inconnu
// se voit attribuer un coût de repli forfaitaire. C'est volontairement
// approximatif — suffisant pour classer/filtrer des recettes par budget,
// pas pour un total de caisse exact.
import { supabase } from '@/lib/supabase';
import type { Recipe } from '@/lib/types';

export const FRACTION_OF_UNIT_PER_RECIPE = 0.3;
export const UNMATCHED_INGREDIENT_FALLBACK_CENTS = 150;

// Repli local si Supabase est injoignable ou que la table est vide
// (ex: avant le premier passage du job quotidien).
export const STATIC_FALLBACK_PRICES_CENTS: Record<string, number> = {
  'œufs': 320,
  lait: 105,
  farine: 95,
  riz: 190,
  'pâtes': 145,
  poulet: 850,
  'bœuf haché': 990,
  tomates: 290,
  oignons: 180,
  'pommes de terre': 165,
  beurre: 220,
  "huile d'olive": 590,
  'fromage râpé': 210,
  'crème fraîche': 165,
  pain: 120,
};

export type PriceMap = Map<string, number>; // ingredient_name -> avg_price_cents

export async function loadPriceMap(): Promise<PriceMap> {
  const map: PriceMap = new Map(Object.entries(STATIC_FALLBACK_PRICES_CENTS));

  const { data, error } = await supabase
    .from('ingredient_price_estimates')
    .select('ingredient_name, avg_price_cents');

  if (!error && data) {
    for (const row of data as { ingredient_name: string; avg_price_cents: number }[]) {
      map.set(row.ingredient_name, row.avg_price_cents);
    }
  }

  return map;
}

export function findMatchingPrice(ingredientName: string, priceMap: PriceMap): number | null {
  const normalized = ingredientName.trim().toLowerCase();
  for (const [name, cents] of priceMap) {
    if (normalized.includes(name.toLowerCase()) || name.toLowerCase().includes(normalized)) {
      return cents;
    }
  }
  return null;
}

export function estimateRecipeCostCents(recipe: Recipe, priceMap: PriceMap): number {
  let total = 0;
  for (const ingredient of recipe.ingredients) {
    const unitPrice = findMatchingPrice(ingredient.name, priceMap);
    total += unitPrice
      ? Math.round(unitPrice * FRACTION_OF_UNIT_PER_RECIPE)
      : UNMATCHED_INGREDIENT_FALLBACK_CENTS;
  }
  return total;
}

export function priceRecipes(recipes: Recipe[], priceMap: PriceMap): Recipe[] {
  return recipes.map((r) => ({ ...r, estimatedCostCents: estimateRecipeCostCents(r, priceMap) }));
}
