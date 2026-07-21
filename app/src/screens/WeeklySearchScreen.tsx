import { Image } from 'expo-image';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/context/AuthContext';
import { usePreferences } from '@/hooks/usePreferences';
import { cacheRecipes } from '@/lib/api/recipeCache';
import { fetchRecipePool } from '@/lib/api/themealdb';
import { loadPriceMap, priceRecipes, type PriceMap } from '@/lib/pricing';
import { buildShoppingList } from '@/lib/planner/buildShoppingList';
import {
  canAddRecipe,
  filterEligibleRecipes,
  remainingBudgetCents,
  totalCostCents,
} from '@/lib/planner/weeklySelection';
import { supabase } from '@/lib/supabase';
import type { Recipe } from '@/lib/types';
import { currentWeekStartISO } from '@/lib/week';
import { OnboardingForm } from '@/screens/OnboardingForm';

// Catégories TheMealDB piochées pour constituer un pool de recettes varié.
const CANDIDATE_CATEGORIES = ['Chicken', 'Beef', 'Pasta', 'Vegetarian', 'Seafood', 'Breakfast', 'Dessert'];

function formatEuros(cents: number): string {
  return (cents / 100).toFixed(2).replace('.', ',') + ' €';
}

export function WeeklySearchScreen() {
  const { session, loading: authLoading } = useAuth();
  const userId = session?.user.id;
  const { preferences, loading: prefsLoading, savePreferences } = usePreferences(userId);

  const [editingPreferences, setEditingPreferences] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [candidates, setCandidates] = useState<Recipe[] | null>(null);
  const [priceMap, setPriceMap] = useState<PriceMap | null>(null);
  const [selection, setSelection] = useState<Recipe[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [validating, setValidating] = useState(false);
  const [confirmation, setConfirmation] = useState<string | null>(null);

  async function handleSavePreferences(draft: Parameters<typeof savePreferences>[0]) {
    setSavingPrefs(true);
    await savePreferences(draft);
    setSavingPrefs(false);
    setEditingPreferences(false);
  }

  async function loadCandidates() {
    if (!preferences) return;
    setLoadingCandidates(true);
    setConfirmation(null);
    try {
      const [pool, prices] = await Promise.all([
        fetchRecipePool(CANDIDATE_CATEGORIES, 6),
        loadPriceMap(),
      ]);
      const priced = priceRecipes(pool, prices);
      setPriceMap(prices);
      setCandidates(filterEligibleRecipes(priced, preferences));
      cacheRecipes(priced);
    } finally {
      setLoadingCandidates(false);
    }
  }

  function toggleSelection(recipe: Recipe) {
    const alreadySelected = selection.some((r) => r.id === recipe.id);
    if (alreadySelected) {
      setSelection(selection.filter((r) => r.id !== recipe.id));
      return;
    }
    if (!preferences || !canAddRecipe(selection, recipe, preferences.weeklyBudgetCents)) return;
    setSelection([...selection, recipe]);
  }

  async function handleValidate() {
    if (!userId || !preferences || !priceMap || selection.length === 0) return;
    setValidating(true);
    try {
      const { data: insertedSelection, error } = await supabase
        .from('weekly_selections')
        .insert({
          user_id: userId,
          week_start: currentWeekStartISO(),
          budget_cents: preferences.weeklyBudgetCents,
          total_cost_cents: totalCostCents(selection),
          store_id: preferences.preferredStoreIds[0] ?? null,
        })
        .select('id')
        .single();

      if (error || !insertedSelection) return;

      await supabase.from('weekly_selection_recipes').insert(
        selection.map((recipe, index) => ({
          selection_id: insertedSelection.id,
          recipe_id: recipe.id,
          position: index,
        })),
      );

      const shoppingList = buildShoppingList(selection, priceMap);
      await supabase.from('shopping_list_items').insert(
        shoppingList.map((item) => ({
          selection_id: insertedSelection.id,
          ingredient_name: item.ingredientName,
          quantity: item.quantity,
          unit: item.unit,
          unit_price_cents: item.unitPriceCents,
          total_price_cents: item.totalPriceCents,
          store_id: preferences.preferredStoreIds[0] ?? null,
        })),
      );

      setConfirmation('Ta semaine est prête ! Retrouve tes recettes et ta liste de courses dans les autres onglets.');
      setCandidates(null);
      setSelection([]);
    } finally {
      setValidating(false);
    }
  }

  if (authLoading || (userId && prefsLoading)) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">Chargement…</ThemedText>
      </ThemedView>
    );
  }

  if (!session) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText>Connecte-toi depuis l&apos;onglet Compte pour composer ton menu.</ThemedText>
      </ThemedView>
    );
  }

  if (!preferences || editingPreferences) {
    return (
      <ScrollView>
        <OnboardingForm onSubmit={handleSavePreferences} submitting={savingPrefs} />
      </ScrollView>
    );
  }

  const total = totalCostCents(selection);
  const remaining = remainingBudgetCents(selection, preferences.weeklyBudgetCents);

  return (
    <View style={styles.flex}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <View>
            <ThemedText type="subtitle">Cette semaine</ThemedText>
            <ThemedText themeColor="textSecondary" type="small">
              Budget : {formatEuros(preferences.weeklyBudgetCents)}
            </ThemedText>
          </View>
          <Pressable onPress={() => setEditingPreferences(true)}>
            <ThemedText type="link">Modifier mes préférences</ThemedText>
          </Pressable>
        </View>

        {confirmation && (
          <ThemedView type="backgroundElement" style={styles.confirmationBanner}>
            <ThemedText type="small">{confirmation}</ThemedText>
          </ThemedView>
        )}

        {candidates === null && (
          <Pressable onPress={loadCandidates} disabled={loadingCandidates}>
            <ThemedView type="backgroundSelected" style={styles.primaryButton}>
              <ThemedText type="smallBold">
                {loadingCandidates ? 'Recherche en cours…' : 'Chercher des recettes pour la semaine'}
              </ThemedText>
            </ThemedView>
          </Pressable>
        )}

        {candidates !== null && candidates.length === 0 && (
          <ThemedText themeColor="textSecondary">
            Aucune recette ne correspond à tes préférences pour l&apos;instant. Essaie d&apos;élargir tes
            équipements ou tes types de repas.
          </ThemedText>
        )}

        <View style={styles.cardList}>
          {candidates?.map((recipe) => {
            const isSelected = selection.some((r) => r.id === recipe.id);
            const affordable = isSelected || canAddRecipe(selection, recipe, preferences.weeklyBudgetCents);
            return (
              <ThemedView key={recipe.id} type="backgroundElement" style={styles.card}>
                {recipe.imageUrl && (
                  <Image source={{ uri: recipe.imageUrl }} style={styles.cardImage} contentFit="cover" />
                )}
                <View style={styles.cardBody}>
                  <ThemedText type="smallBold">{recipe.title}</ThemedText>
                  <ThemedText type="small" themeColor="textSecondary">
                    ≈ {formatEuros(recipe.estimatedCostCents)}
                  </ThemedText>
                </View>
                <Pressable onPress={() => toggleSelection(recipe)} disabled={!affordable}>
                  <ThemedView
                    type={isSelected ? 'backgroundSelected' : 'background'}
                    style={[styles.addButton, !affordable && styles.disabled]}>
                    <ThemedText type="small">{isSelected ? 'Retirer' : 'Ajouter'}</ThemedText>
                  </ThemedView>
                </Pressable>
              </ThemedView>
            );
          })}
        </View>
      </ScrollView>

      {selection.length > 0 && (
        <ThemedView type="backgroundElement" style={styles.footer}>
          <View>
            <ThemedText type="smallBold">
              {selection.length} plat{selection.length > 1 ? 's' : ''} · {formatEuros(total)}
            </ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              Reste {formatEuros(Math.max(remaining, 0))} sur le budget
            </ThemedText>
          </View>
          <Pressable onPress={handleValidate} disabled={validating}>
            <ThemedView type="backgroundSelected" style={styles.primaryButton}>
              <ThemedText type="smallBold">{validating ? 'Validation…' : 'Valider ma semaine'}</ThemedText>
            </ThemedView>
          </Pressable>
        </ThemedView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.four,
  },
  scrollContent: {
    padding: Spacing.four,
    gap: Spacing.three,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  confirmationBanner: {
    padding: Spacing.three,
    borderRadius: Spacing.three,
  },
  primaryButton: {
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.four,
    borderRadius: Spacing.five,
    alignItems: 'center',
  },
  cardList: {
    gap: Spacing.three,
  },
  card: {
    borderRadius: Spacing.three,
    overflow: 'hidden',
  },
  cardImage: {
    width: '100%',
    height: 160,
  },
  cardBody: {
    padding: Spacing.three,
    gap: Spacing.one,
  },
  addButton: {
    marginHorizontal: Spacing.three,
    marginBottom: Spacing.three,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.three,
    alignItems: 'center',
  },
  disabled: {
    opacity: 0.4,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.three,
  },
});
