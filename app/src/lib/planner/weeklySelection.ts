// Logique pure de sélection hebdomadaire : le principe retenu (cf. brief
// produit) est que l'utilisateur choisit lui-même ses plats un par un dans
// la liste des recettes éligibles, avec un total qui ne doit jamais
// dépasser son budget hebdomadaire. Ce module ne fait que filtrer les
// recettes éligibles et calculer les totaux ; l'écran gère l'état de la
// sélection en cours.
import type { Recipe, UserPreferences } from '@/lib/types';

export function filterEligibleRecipes(recipes: Recipe[], prefs: UserPreferences): Recipe[] {
  return recipes.filter((recipe) => {
    const hasDislikedIngredient = recipe.ingredients.some((ingredient) =>
      prefs.dislikedIngredients.some((disliked) =>
        ingredient.name.toLowerCase().includes(disliked.toLowerCase()),
      ),
    );
    if (hasDislikedIngredient) return false;

    const missingEquipment = recipe.equipmentRequired.some(
      (required) => !prefs.equipment.includes(required),
    );
    if (missingEquipment) return false;

    if (prefs.mealTypes.length > 0) {
      const matchesMealType = recipe.mealTypes.some((type) => prefs.mealTypes.includes(type));
      if (!matchesMealType) return false;
    }

    return true;
  });
}

export function totalCostCents(selection: Recipe[]): number {
  return selection.reduce((sum, recipe) => sum + recipe.estimatedCostCents, 0);
}

export function remainingBudgetCents(selection: Recipe[], budgetCents: number): number {
  return budgetCents - totalCostCents(selection);
}

export function canAddRecipe(selection: Recipe[], candidate: Recipe, budgetCents: number): boolean {
  return totalCostCents(selection) + candidate.estimatedCostCents <= budgetCents;
}
