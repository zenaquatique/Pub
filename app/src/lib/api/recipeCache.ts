import { supabase } from '@/lib/supabase';
import type { Recipe } from '@/lib/types';

interface RecipeRow {
  id: string;
  source: string;
  title: string;
  image_url: string | null;
  category: string | null;
  area: string | null;
  instructions: string;
  ingredients: Recipe['ingredients'];
  equipment_required: Recipe['equipmentRequired'];
  meal_types: Recipe['mealTypes'];
}

function toRow(recipe: Recipe): RecipeRow {
  return {
    id: recipe.id,
    source: recipe.source,
    title: recipe.title,
    image_url: recipe.imageUrl,
    category: recipe.category,
    area: recipe.area,
    instructions: recipe.instructions,
    ingredients: recipe.ingredients,
    equipment_required: recipe.equipmentRequired,
    meal_types: recipe.mealTypes,
  };
}

function fromRow(row: RecipeRow): Recipe {
  return {
    id: row.id,
    source: row.source,
    title: row.title,
    imageUrl: row.image_url,
    category: row.category,
    area: row.area,
    instructions: row.instructions,
    ingredients: row.ingredients,
    equipmentRequired: row.equipment_required,
    mealTypes: row.meal_types,
    estimatedCostCents: 0,
  };
}

/** Alimente le cache partagé public.recipes (best-effort, ne bloque pas l'UI en cas d'échec). */
export async function cacheRecipes(recipes: Recipe[]): Promise<void> {
  if (recipes.length === 0) return;
  await supabase.from('recipes').upsert(recipes.map(toRow));
}

export async function fetchRecipesByIds(ids: string[]): Promise<Recipe[]> {
  if (ids.length === 0) return [];
  const { data } = await supabase.from('recipes').select('*').in('id', ids);
  return (data as RecipeRow[] | null)?.map(fromRow) ?? [];
}
