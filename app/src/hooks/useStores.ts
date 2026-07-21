import { useEffect, useState } from 'react';

import { supabase } from '@/lib/supabase';
import type { Store } from '@/lib/types';

export function useStores() {
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    supabase
      .from('stores')
      .select('id, slug, name')
      .order('name')
      .then(({ data }) => {
        if (cancelled) return;
        setStores(data ?? []);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { stores, loading };
}
