import { useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/context/AuthContext';

export function AccountScreen() {
  const { session, loading, signIn, signUp, signOut } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'signIn' | 'signUp'>('signIn');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    const result = mode === 'signIn' ? await signIn(email, password) : await signUp(email, password);
    if (result) setError(result);
    setSubmitting(false);
  }

  if (loading) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">Chargement…</ThemedText>
      </ThemedView>
    );
  }

  if (session) {
    return (
      <ThemedView style={styles.container}>
        <ThemedText type="subtitle">Mon compte</ThemedText>
        <ThemedText themeColor="textSecondary">{session.user.email}</ThemedText>
        <Pressable onPress={signOut}>
          <ThemedView type="backgroundElement" style={styles.button}>
            <ThemedText type="smallBold">Se déconnecter</ThemedText>
          </ThemedView>
        </Pressable>
      </ThemedView>
    );
  }

  return (
    <ThemedView style={styles.container}>
      <ThemedText type="subtitle">{mode === 'signIn' ? 'Connexion' : 'Créer un compte'}</ThemedText>

      <View style={styles.field}>
        <ThemedText type="small" themeColor="textSecondary">
          Email
        </ThemedText>
        <TextInput
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
          style={styles.input}
        />
      </View>

      <View style={styles.field}>
        <ThemedText type="small" themeColor="textSecondary">
          Mot de passe
        </ThemedText>
        <TextInput value={password} onChangeText={setPassword} secureTextEntry style={styles.input} />
      </View>

      {error && (
        <ThemedText type="small" themeColor="text">
          {error}
        </ThemedText>
      )}

      <Pressable onPress={handleSubmit} disabled={submitting}>
        <ThemedView type="backgroundSelected" style={styles.button}>
          <ThemedText type="smallBold">
            {submitting ? 'Patiente…' : mode === 'signIn' ? 'Se connecter' : "S'inscrire"}
          </ThemedText>
        </ThemedView>
      </Pressable>

      <Pressable onPress={() => setMode(mode === 'signIn' ? 'signUp' : 'signIn')}>
        <ThemedText type="link">
          {mode === 'signIn' ? 'Pas encore de compte ? Inscris-toi' : 'Déjà un compte ? Connecte-toi'}
        </ThemedText>
      </Pressable>
    </ThemedView>
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
    flex: 1,
    padding: Spacing.four,
    gap: Spacing.three,
    justifyContent: 'center',
  },
  field: {
    gap: Spacing.one,
  },
  input: {
    fontSize: 16,
    borderBottomWidth: 2,
    borderColor: '#3c87f7',
    paddingVertical: Spacing.two,
  },
  button: {
    paddingVertical: Spacing.three,
    borderRadius: Spacing.five,
    alignItems: 'center',
  },
});
