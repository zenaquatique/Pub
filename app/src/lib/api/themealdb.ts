// Client pour TheMealDB (https://www.themealdb.com), source de recettes
// gratuite utilisée pour la V1. La clé "1" est la clé de test publique
// fournie par TheMealDB pour un usage non commercial à faible volume ;
// à remplacer par une clé Patreon si le volume de requêtes augmente.
import type { EquipmentValue, MealTypeValue, Recipe, RecipeIngredient } from '@/lib/types';

const BASE_URL = 'https://www.themealdb.com/api/json/v1/1';

interface RawMeal {
  idMeal: string;
  strMeal: string;
  strCategory: string | null;
  strArea: string | null;
  strInstructions: string | null;
  strMealThumb: string | null;
  [key: `strIngredient${number}`]: string | null | undefined;
  [key: `strMeasure${number}`]: string | null | undefined;
}

const CATEGORY_TO_MEAL_TYPES: Record<string, MealTypeValue[]> = {
  Breakfast: ['petit-dejeuner'],
  Dessert: ['dessert'],
  Vegetarian: ['vegetarien'],
  Vegan: ['vegetarien'],
  Starter: ['dejeuner', 'diner'],
  Side: ['dejeuner', 'diner'],
};

const EQUIPMENT_KEYWORDS: { keyword: RegExp; equipment: EquipmentValue }[] = [
  { keyword: /oven|bake|roast/i, equipment: 'four' },
  { keyword: /microwave/i, equipment: 'micro-ondes' },
  { keyword: /blend|purée|puree/i, equipment: 'mixeur' },
  { keyword: /food processor/i, equipment: 'robot-cuisine' },
  { keyword: /fry(?!ing pan)|deep-fry/i, equipment: 'friteuse' },
  { keyword: /pressure cooker/i, equipment: 'autocuiseur' },
  { keyword: /grill|barbecue|bbq/i, equipment: 'grill' },
  { keyword: /steam/i, equipment: 'cuiseur-vapeur' },
];

function inferMealTypes(category: string | null): MealTypeValue[] {
  if (category && CATEGORY_TO_MEAL_TYPES[category]) return CATEGORY_TO_MEAL_TYPES[category];
  return ['dejeuner', 'diner'];
}

function inferEquipment(instructions: string | null): EquipmentValue[] {
  if (!instructions) return [];
  const found = new Set<EquipmentValue>();
  for (const { keyword, equipment } of EQUIPMENT_KEYWORDS) {
    if (keyword.test(instructions)) found.add(equipment);
  }
  return [...found];
}

function extractIngredients(raw: RawMeal): RecipeIngredient[] {
  const ingredients: RecipeIngredient[] = [];
  for (let i = 1; i <= 20; i += 1) {
    const name = raw[`strIngredient${i}`]?.trim();
    const measure = raw[`strMeasure${i}`]?.trim();
    if (name) ingredients.push({ name, measure: measure || '' });
  }
  return ingredients;
}

export function normalizeMeal(raw: RawMeal): Recipe {
  return {
    id: `themealdb:${raw.idMeal}`,
    source: 'themealdb',
    title: raw.strMeal,
    imageUrl: raw.strMealThumb,
    category: raw.strCategory,
    area: raw.strArea,
    instructions: raw.strInstructions ?? '',
    ingredients: extractIngredients(raw),
    equipmentRequired: inferEquipment(raw.strInstructions),
    mealTypes: inferMealTypes(raw.strCategory),
    estimatedCostCents: 0, // calculé séparément, voir lib/pricing.ts
  };
}

export async function listCategories(): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/list.php?c=list`);
  const data = (await res.json()) as { meals: { strCategory: string }[] };
  return data.meals.map((m) => m.strCategory);
}

export async function fetchMealIdsByCategory(category: string): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/filter.php?c=${encodeURIComponent(category)}`);
  const data = (await res.json()) as { meals: { idMeal: string }[] | null };
  return (data.meals ?? []).map((m) => m.idMeal);
}

export async function fetchMealById(id: string): Promise<Recipe | null> {
  const res = await fetch(`${BASE_URL}/lookup.php?i=${id}`);
  const data = (await res.json()) as { meals: RawMeal[] | null };
  const meal = data.meals?.[0];
  return meal ? normalizeMeal(meal) : null;
}

/** Récupère un lot de recettes réparties sur plusieurs catégories pour varier l'offre. */
export async function fetchRecipePool(categories: string[], perCategory = 8): Promise<Recipe[]> {
  const recipes: Recipe[] = [];
  for (const category of categories) {
    const ids = (await fetchMealIdsByCategory(category)).slice(0, perCategory);
    const details = await Promise.all(ids.map(fetchMealById));
    recipes.push(...details.filter((r): r is Recipe => r !== null));
  }
  return recipes;
}
