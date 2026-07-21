import { Image } from 'expo-image';
import { ScrollView, StyleSheet, View } from 'react-native';

import { Collapsible } from '@/components/ui/collapsible';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/context/AuthContext';
import { useLatestSelection } from '@/hooks/useLatestSelection';

export function RecipesScreen() {
  const { session } = useAuth();
  const { selection, loading } = useLatestSelection(session?.user.id);

  if (!session) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText>Connecte-toi pour retrouver tes recettes de la semaine.</ThemedText>
      </ThemedView>
    );
  }

  if (loading) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">Chargement…</ThemedText>
      </ThemedView>
    );
  }

  if (!selection || selection.recipes.length === 0) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">
          Aucune recette pour l&apos;instant. Compose ton menu depuis l&apos;onglet &laquo; Cette semaine
          &raquo;.
        </ThemedText>
      </ThemedView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <ThemedText type="subtitle">Tes recettes de la semaine</ThemedText>
      {selection.recipes.map((recipe) => (
        <ThemedView key={recipe.id} type="backgroundElement" style={styles.card}>
          {recipe.imageUrl && (
            <Image source={{ uri: recipe.imageUrl }} style={styles.image} contentFit="cover" />
          )}
          <View style={styles.body}>
            <ThemedText type="smallBold">{recipe.title}</ThemedText>

            <Collapsible title="Ingrédients">
              {recipe.ingredients.map((ingredient) => (
                <ThemedText key={ingredient.name} type="small">
                  • {ingredient.measure} {ingredient.name}
                </ThemedText>
              ))}
            </Collapsible>

            <Collapsible title="Préparation">
              <ThemedText type="small">{recipe.instructions}</ThemedText>
            </Collapsible>
          </View>
        </ThemedView>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.four,
  },
  container: {
    padding: Spacing.four,
    gap: Spacing.three,
  },
  card: {
    borderRadius: Spacing.three,
    overflow: 'hidden',
  },
  image: {
    width: '100%',
    height: 180,
  },
  body: {
    padding: Spacing.three,
    gap: Spacing.two,
  },
});
