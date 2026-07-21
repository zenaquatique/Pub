import {
  findMatchingPrice,
  FRACTION_OF_UNIT_PER_RECIPE,
  UNMATCHED_INGREDIENT_FALLBACK_CENTS,
  type PriceMap,
} from '@/lib/pricing';
import type { Recipe, ShoppingListItem } from '@/lib/types';

/**
 * Agrège les ingrédients des recettes sélectionnées en une liste de courses.
 * Le prix de chaque article suit la même heuristique que l'estimation de
 * coût par recette (voir lib/pricing.ts), afin que le total de la liste de
 * courses corresponde exactement à la somme des coûts estimés des recettes.
 */
export function buildShoppingList(recipes: Recipe[], priceMap: PriceMap): ShoppingListItem[] {
  const byIngredient = new Map<string, { measures: string[]; occurrences: number }>();

  for (const recipe of recipes) {
    for (const ingredient of recipe.ingredients) {
      const key = ingredient.name.trim().toLowerCase();
      const entry = byIngredient.get(key) ?? { measures: [], occurrences: 0 };
      entry.occurrences += 1;
      if (ingredient.measure) entry.measures.push(ingredient.measure);
      byIngredient.set(key, entry);
    }
  }

  const items: ShoppingListItem[] = [];
  for (const [ingredientName, { measures, occurrences }] of byIngredient) {
    const unitPriceCents = findMatchingPrice(ingredientName, priceMap);
    const perUsageCents = unitPriceCents
      ? Math.round(unitPriceCents * FRACTION_OF_UNIT_PER_RECIPE)
      : UNMATCHED_INGREDIENT_FALLBACK_CENTS;

    items.push({
      ingredientName,
      quantity: occurrences,
      unit: measures[0] || 'recette(s)',
      unitPriceCents: perUsageCents,
      totalPriceCents: perUsageCents * occurrences,
      storeId: null,
      purchased: false,
    });
  }

  return items.sort((a, b) => a.ingredientName.localeCompare(b.ingredientName));
}
