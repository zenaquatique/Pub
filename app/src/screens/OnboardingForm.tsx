import { useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { Chip } from '@/components/chip';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useStores } from '@/hooks/useStores';
import {
  EQUIPMENT_OPTIONS,
  MEAL_TYPE_OPTIONS,
  type EquipmentValue,
  type MealTypeValue,
  type UserPreferences,
} from '@/lib/types';

type Draft = Omit<UserPreferences, 'userId' | 'updatedAt'>;

const STEPS = ['budget', 'stores', 'equipment', 'disliked', 'mealTypes'] as const;

export function OnboardingForm({
  onSubmit,
  submitting,
}: {
  onSubmit: (draft: Draft) => void;
  submitting: boolean;
}) {
  const { stores } = useStores();
  const [stepIndex, setStepIndex] = useState(0);
  const [budgetInput, setBudgetInput] = useState('40');
  const [storeIds, setStoreIds] = useState<string[]>([]);
  const [equipment, setEquipment] = useState<EquipmentValue[]>([]);
  const [dislikedInput, setDislikedInput] = useState('');
  const [disliked, setDisliked] = useState<string[]>([]);
  const [mealTypes, setMealTypes] = useState<MealTypeValue[]>([]);

  const step = STEPS[stepIndex];
  const isLastStep = stepIndex === STEPS.length - 1;

  function toggle<T>(list: T[], value: T, setList: (v: T[]) => void) {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  function addDislikedIngredient() {
    const trimmed = dislikedInput.trim();
    if (!trimmed || disliked.includes(trimmed)) return;
    setDisliked([...disliked, trimmed]);
    setDislikedInput('');
  }

  function handleNext() {
    if (isLastStep) {
      onSubmit({
        weeklyBudgetCents: Math.round((parseFloat(budgetInput.replace(',', '.')) || 0) * 100),
        preferredStoreIds: storeIds,
        equipment,
        dislikedIngredients: disliked,
        mealTypes,
      });
      return;
    }
    setStepIndex(stepIndex + 1);
  }

  return (
    <ThemedView style={styles.container}>
      <ThemedText type="subtitle">Personnalise ton menu</ThemedText>
      <ThemedText type="small" themeColor="textSecondary" style={styles.stepCounter}>
        Étape {stepIndex + 1} sur {STEPS.length}
      </ThemedText>

      {step === 'budget' && (
        <View style={styles.stepBody}>
          <ThemedText>Quel budget veux-tu consacrer aux repas cette semaine ?</ThemedText>
          <View style={styles.budgetRow}>
            <TextInput
              value={budgetInput}
              onChangeText={setBudgetInput}
              keyboardType="decimal-pad"
              style={styles.budgetInput}
              placeholder="40"
            />
            <ThemedText type="subtitle">€</ThemedText>
          </View>
        </View>
      )}

      {step === 'stores' && (
        <View style={styles.stepBody}>
          <ThemedText>Dans quels magasins fais-tu tes courses ?</ThemedText>
          <View style={styles.chipRow}>
            {stores.map((store) => (
              <Chip
                key={store.id}
                label={store.name}
                selected={storeIds.includes(store.id)}
                onPress={() => toggle(storeIds, store.id, setStoreIds)}
              />
            ))}
          </View>
        </View>
      )}

      {step === 'equipment' && (
        <View style={styles.stepBody}>
          <ThemedText>Qu&apos;as-tu comme équipement de cuisine ?</ThemedText>
          <View style={styles.chipRow}>
            {EQUIPMENT_OPTIONS.map((option) => (
              <Chip
                key={option.value}
                label={option.label}
                selected={equipment.includes(option.value)}
                onPress={() => toggle(equipment, option.value, setEquipment)}
              />
            ))}
          </View>
        </View>
      )}

      {step === 'disliked' && (
        <View style={styles.stepBody}>
          <ThemedText>Y a-t-il des aliments que tu n&apos;aimes pas ?</ThemedText>
          <View style={styles.budgetRow}>
            <TextInput
              value={dislikedInput}
              onChangeText={setDislikedInput}
              onSubmitEditing={addDislikedIngredient}
              style={styles.textInput}
              placeholder="ex : champignons"
            />
            <Pressable onPress={addDislikedIngredient}>
              <ThemedView type="backgroundElement" style={styles.addButton}>
                <ThemedText type="smallBold">Ajouter</ThemedText>
              </ThemedView>
            </Pressable>
          </View>
          <View style={styles.chipRow}>
            {disliked.map((item) => (
              <Chip
                key={item}
                label={`${item} ✕`}
                selected
                onPress={() => setDisliked(disliked.filter((d) => d !== item))}
              />
            ))}
          </View>
        </View>
      )}

      {step === 'mealTypes' && (
        <View style={styles.stepBody}>
          <ThemedText>Quels types de repas veux-tu ?</ThemedText>
          <View style={styles.chipRow}>
            {MEAL_TYPE_OPTIONS.map((option) => (
              <Chip
                key={option.value}
                label={option.label}
                selected={mealTypes.includes(option.value)}
                onPress={() => toggle(mealTypes, option.value, setMealTypes)}
              />
            ))}
          </View>
        </View>
      )}

      <View style={styles.navRow}>
        {stepIndex > 0 && (
          <Pressable onPress={() => setStepIndex(stepIndex - 1)}>
            <ThemedText type="link">Précédent</ThemedText>
          </Pressable>
        )}
        <Pressable onPress={handleNext} disabled={submitting} style={styles.nextButtonWrapper}>
          <ThemedView type="backgroundSelected" style={styles.nextButton}>
            <ThemedText type="smallBold">
              {isLastStep ? (submitting ? 'Enregistrement…' : 'Terminer') : 'Suivant'}
            </ThemedText>
          </ThemedView>
        </Pressable>
      </View>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Spacing.three,
    padding: Spacing.four,
  },
  stepCounter: {
    marginBottom: Spacing.two,
  },
  stepBody: {
    gap: Spacing.three,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
  budgetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  budgetInput: {
    fontSize: 32,
    fontWeight: '600',
    borderBottomWidth: 2,
    borderColor: '#3c87f7',
    paddingVertical: Spacing.one,
    minWidth: 100,
  },
  textInput: {
    flex: 1,
    fontSize: 16,
    borderBottomWidth: 2,
    borderColor: '#3c87f7',
    paddingVertical: Spacing.one,
  },
  addButton: {
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.three,
    borderRadius: Spacing.three,
  },
  navRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: Spacing.four,
  },
  nextButtonWrapper: {
    marginLeft: 'auto',
  },
  nextButton: {
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.four,
    borderRadius: Spacing.five,
  },
});
