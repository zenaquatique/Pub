// Edge Function planifiée quotidiennement à 6h (Europe/Paris) par
// supabase/migrations/0002_daily_refresh_schedule.sql.
//
// Récupère les prix moyens communautaires depuis Open Prices
// (https://prices.openfoodfacts.org/api/docs), pour la France, sur une
// liste d'ingrédients génériques, et met à jour
// public.ingredient_price_estimates. Sert de repli quand aucune source de
// prix par magasin n'est disponible.

import { createClient } from 'jsr:@supabase/supabase-js@2';

const OPEN_PRICES_API = 'https://prices.openfoodfacts.org/api/v1';
const REFRESH_MIN_INTERVAL_HOURS = 12;

// Ingrédients génériques couverts en V1 (nom -> termes de recherche Open
// Prices + unité de référence pour l'estimation de budget).
const TRACKED_INGREDIENTS: { name: string; query: string; unit: string }[] = [
  { name: 'œufs', query: 'oeufs', unit: 'boîte de 6' },
  { name: 'lait', query: 'lait demi-écrémé', unit: 'litre' },
  { name: 'farine', query: 'farine de blé', unit: 'kg' },
  { name: 'riz', query: 'riz', unit: 'kg' },
  { name: 'pâtes', query: 'pâtes', unit: 'kg' },
  { name: 'poulet', query: 'blanc de poulet', unit: 'kg' },
  { name: 'bœuf haché', query: 'steak haché', unit: 'kg' },
  { name: 'tomates', query: 'tomates', unit: 'kg' },
  { name: 'oignons', query: 'oignons', unit: 'kg' },
  { name: 'pommes de terre', query: 'pommes de terre', unit: 'kg' },
  { name: 'beurre', query: 'beurre', unit: '250g' },
  { name: 'huile d\'olive', query: 'huile d\'olive', unit: 'litre' },
  { name: 'fromage râpé', query: 'emmental râpé', unit: '200g' },
  { name: 'crème fraîche', query: 'crème fraîche', unit: '20cl' },
  { name: 'pain', query: 'pain', unit: 'unité' },
];

interface OpenPricesResult {
  items: { price: number; currency: string }[];
}

async function fetchAveragePrice(query: string): Promise<number | null> {
  const url = `${OPEN_PRICES_API}/prices?product_name=${encodeURIComponent(query)}&locations__country_code=fr&currency=EUR&size=20`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) return null;

  const data = (await res.json()) as OpenPricesResult;
  const prices = data.items?.map((item) => item.price).filter((p) => typeof p === 'number');
  if (!prices || prices.length === 0) return null;

  const avg = prices.reduce((sum, p) => sum + p, 0) / prices.length;
  return Math.round(avg * 100); // en centimes
}

Deno.serve(async (req) => {
  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  );

  const { data: mostRecent } = await supabase
    .from('ingredient_price_estimates')
    .select('updated_at')
    .order('updated_at', { ascending: false })
    .limit(1)
    .maybeSingle();

  if (mostRecent?.updated_at) {
    const hoursSinceRefresh = (Date.now() - new Date(mostRecent.updated_at).getTime()) / 3_600_000;
    if (hoursSinceRefresh < REFRESH_MIN_INTERVAL_HOURS) {
      return Response.json({ skipped: true, reason: 'refreshed recently' });
    }
  }

  const results: { name: string; ok: boolean }[] = [];

  for (const ingredient of TRACKED_INGREDIENTS) {
    try {
      const avgPriceCents = await fetchAveragePrice(ingredient.query);
      if (avgPriceCents === null) {
        results.push({ name: ingredient.name, ok: false });
        continue;
      }

      await supabase.from('ingredient_price_estimates').upsert({
        ingredient_name: ingredient.name,
        unit: ingredient.unit,
        avg_price_cents: avgPriceCents,
        currency: 'EUR',
        source: 'open-prices',
        updated_at: new Date().toISOString(),
      });
      results.push({ name: ingredient.name, ok: true });
    } catch {
      results.push({ name: ingredient.name, ok: false });
    }
  }

  return Response.json({ skipped: false, results });
});
