export interface Store {
  id: string;
  slug: string;
  name: string;
}

export const EQUIPMENT_OPTIONS = [
  { value: 'four', label: 'Four' },
  { value: 'plaques-cuisson', label: 'Plaques de cuisson' },
  { value: 'micro-ondes', label: 'Micro-ondes' },
  { value: 'mixeur', label: 'Mixeur / blender' },
  { value: 'robot-cuisine', label: 'Robot de cuisine' },
  { value: 'friteuse', label: 'Friteuse' },
  { value: 'autocuiseur', label: 'Autocuiseur / cocotte-minute' },
  { value: 'grill', label: 'Grill / barbecue' },
  { value: 'cuiseur-vapeur', label: 'Cuiseur vapeur' },
] as const;

export type EquipmentValue = (typeof EQUIPMENT_OPTIONS)[number]['value'];

export const MEAL_TYPE_OPTIONS = [
  { value: 'petit-dejeuner', label: 'Petit-déjeuner' },
  { value: 'dejeuner', label: 'Déjeuner' },
  { value: 'diner', label: 'Dîner' },
  { value: 'dessert', label: 'Dessert' },
  { value: 'vegetarien', label: 'Végétarien' },
] as const;

export type MealTypeValue = (typeof MEAL_TYPE_OPTIONS)[number]['value'];

export interface UserPreferences {
  userId: string;
  weeklyBudgetCents: number;
  preferredStoreIds: string[];
  equipment: EquipmentValue[];
  dislikedIngredients: string[];
  mealTypes: MealTypeValue[];
  updatedAt: string;
}

export interface RecipeIngredient {
  name: string;
  measure: string;
}

export interface Recipe {
  id: string;
  source: string;
  title: string;
  imageUrl: string | null;
  category: string | null;
  area: string | null;
  instructions: string;
  ingredients: RecipeIngredient[];
  equipmentRequired: EquipmentValue[];
  mealTypes: MealTypeValue[];
  /** Estimation grossière du coût de la recette, en centimes. */
  estimatedCostCents: number;
}

export interface WeeklySelection {
  id: string;
  userId: string;
  weekStart: string;
  budgetCents: number;
  totalCostCents: number;
  storeId: string | null;
  recipes: Recipe[];
}

export interface ShoppingListItem {
  ingredientName: string;
  quantity: number;
  unit: string;
  unitPriceCents: number;
  totalPriceCents: number;
  storeId: string | null;
  purchased: boolean;
}

export interface IngredientPriceEstimate {
  ingredientName: string;
  unit: string;
  avgPriceCents: number;
  currency: string;
  source: string;
  updatedAt: string;
}
