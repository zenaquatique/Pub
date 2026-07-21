import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/context/AuthContext';
import { useLatestSelection } from '@/hooks/useLatestSelection';
import { supabase } from '@/lib/supabase';

interface ShoppingListItemRow {
  id: string;
  ingredient_name: string;
  quantity: number;
  unit: string;
  total_price_cents: number;
  purchased: boolean;
}

function formatEuros(cents: number): string {
  return (cents / 100).toFixed(2).replace('.', ',') + ' €';
}

export function ShoppingListScreen() {
  const { session } = useAuth();
  const { selection, loading: selectionLoading } = useLatestSelection(session?.user.id);
  const [items, setItems] = useState<ShoppingListItemRow[]>([]);
  const [loadingItems, setLoadingItems] = useState(true);

  useEffect(() => {
    if (!selection) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reset on selection change
      setItems([]);
      setLoadingItems(false);
      return;
    }
    setLoadingItems(true);
    supabase
      .from('shopping_list_items')
      .select('id, ingredient_name, quantity, unit, total_price_cents, purchased')
      .eq('selection_id', selection.id)
      .order('ingredient_name')
      .then(({ data }) => {
        setItems(data ?? []);
        setLoadingItems(false);
      });
  }, [selection]);

  async function togglePurchased(item: ShoppingListItemRow) {
    setItems(items.map((i) => (i.id === item.id ? { ...i, purchased: !i.purchased } : i)));
    await supabase.from('shopping_list_items').update({ purchased: !item.purchased }).eq('id', item.id);
  }

  if (!session) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText>Connecte-toi pour retrouver ta liste de courses.</ThemedText>
      </ThemedView>
    );
  }

  if (selectionLoading || loadingItems) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">Chargement…</ThemedText>
      </ThemedView>
    );
  }

  if (!selection || items.length === 0) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">
          Ta liste de courses apparaîtra ici une fois ta semaine validée.
        </ThemedText>
      </ThemedView>
    );
  }

  const total = items.reduce((sum, item) => sum + item.total_price_cents, 0);

  return (
    <View style={styles.flex}>
      <ScrollView contentContainerStyle={styles.container}>
        <ThemedText type="subtitle">Liste de courses</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          Estimation — les prix précis dépendent de la couverture Open Prices pour ton magasin.
        </ThemedText>
        {items.map((item) => (
          <Pressable key={item.id} onPress={() => togglePurchased(item)}>
            <ThemedView type="backgroundElement" style={styles.row}>
              <View style={styles.rowText}>
                <ThemedText
                  type="small"
                  style={item.purchased ? styles.strikethrough : undefined}
                  themeColor={item.purchased ? 'textSecondary' : 'text'}>
                  {item.quantity > 1 ? `${item.quantity}× ` : ''}
                  {item.ingredient_name}
                </ThemedText>
              </View>
              <ThemedText type="small" themeColor="textSecondary">
                {formatEuros(item.total_price_cents)}
              </ThemedText>
            </ThemedView>
          </Pressable>
        ))}
      </ScrollView>
      <ThemedView type="backgroundElement" style={styles.footer}>
        <ThemedText type="smallBold">Total estimé : {formatEuros(total)}</ThemedText>
      </ThemedView>
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
  container: {
    padding: Spacing.four,
    gap: Spacing.two,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.three,
    borderRadius: Spacing.three,
  },
  rowText: {
    flex: 1,
  },
  strikethrough: {
    textDecorationLine: 'line-through',
  },
  footer: {
    padding: Spacing.three,
    alignItems: 'center',
  },
});
