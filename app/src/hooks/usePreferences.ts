import { useCallback, useEffect, useState } from 'react';

import { supabase } from '@/lib/supabase';
import type { EquipmentValue, MealTypeValue, UserPreferences } from '@/lib/types';

interface PreferencesRow {
  user_id: string;
  weekly_budget_cents: number;
  preferred_store_ids: string[];
  equipment: string[];
  disliked_ingredients: string[];
  meal_types: string[];
  updated_at: string;
}

function fromRow(row: PreferencesRow): UserPreferences {
  return {
    userId: row.user_id,
    weeklyBudgetCents: row.weekly_budget_cents,
    preferredStoreIds: row.preferred_store_ids,
    equipment: row.equipment as EquipmentValue[],
    dislikedIngredients: row.disliked_ingredients,
    mealTypes: row.meal_types as MealTypeValue[],
    updatedAt: row.updated_at,
  };
}

export function usePreferences(userId: string | undefined) {
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!userId) {
      setPreferences(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    const { data } = await supabase
      .from('user_preferences')
      .select('*')
      .eq('user_id', userId)
      .maybeSingle();
    setPreferences(data ? fromRow(data as PreferencesRow) : null);
    setLoading(false);
  }, [userId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch on mount/user change
    reload();
  }, [reload]);

  const savePreferences = useCallback(
    async (prefs: Omit<UserPreferences, 'userId' | 'updatedAt'>) => {
      if (!userId) return;
      const { error } = await supabase.from('user_preferences').upsert({
        user_id: userId,
        weekly_budget_cents: prefs.weeklyBudgetCents,
        preferred_store_ids: prefs.preferredStoreIds,
        equipment: prefs.equipment,
        disliked_ingredients: prefs.dislikedIngredients,
        meal_types: prefs.mealTypes,
        updated_at: new Date().toISOString(),
      });
      if (!error) await reload();
      return error?.message ?? null;
    },
    [userId, reload],
  );

  return { preferences, loading, savePreferences };
}
