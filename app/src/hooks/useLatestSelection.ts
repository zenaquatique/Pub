import { useCallback, useEffect, useState } from 'react';

import { fetchRecipesByIds } from '@/lib/api/recipeCache';
import { supabase } from '@/lib/supabase';
import type { WeeklySelection } from '@/lib/types';

export function useLatestSelection(userId: string | undefined) {
  const [selection, setSelection] = useState<WeeklySelection | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!userId) {
      setSelection(null);
      setLoading(false);
      return;
    }
    setLoading(true);

    const { data: selectionRow } = await supabase
      .from('weekly_selections')
      .select('id, user_id, week_start, budget_cents, total_cost_cents, store_id')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (!selectionRow) {
      setSelection(null);
      setLoading(false);
      return;
    }

    const { data: linkRows } = await supabase
      .from('weekly_selection_recipes')
      .select('recipe_id, position')
      .eq('selection_id', selectionRow.id)
      .order('position');

    const recipeIds = (linkRows ?? []).map((row) => row.recipe_id as string);
    const recipes = await fetchRecipesByIds(recipeIds);
    const orderedRecipes = recipeIds
      .map((id) => recipes.find((r) => r.id === id))
      .filter((r): r is NonNullable<typeof r> => r !== undefined);

    setSelection({
      id: selectionRow.id,
      userId: selectionRow.user_id,
      weekStart: selectionRow.week_start,
      budgetCents: selectionRow.budget_cents,
      totalCostCents: selectionRow.total_cost_cents,
      storeId: selectionRow.store_id,
      recipes: orderedRecipes,
    });
    setLoading(false);
  }, [userId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch on mount/user change
    reload();
  }, [reload]);

  return { selection, loading, reload };
}
