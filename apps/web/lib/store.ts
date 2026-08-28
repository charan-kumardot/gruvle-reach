import { useEffect, useState } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { setToken } from "./api-client";
import type { Organization, Product, Workspace } from "./types";

interface AppState {
  token: string | null;
  userEmail: string | null;
  organization: Organization | null;
  workspace: Workspace | null;
  product: Product | null;
  setAuth: (token: string, userEmail: string) => void;
  setOrganization: (org: Organization) => void;
  setWorkspace: (ws: Workspace) => void;
  setProduct: (product: Product | null) => void;
  logout: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      token: null,
      userEmail: null,
      organization: null,
      workspace: null,
      product: null,
      setAuth: (token, userEmail) => {
        setToken(token);
        set({ token, userEmail });
      },
      setOrganization: (organization) => set({ organization, workspace: null, product: null }),
      setWorkspace: (workspace) => set({ workspace, product: null }),
      setProduct: (product) => set({ product }),
      logout: () => {
        setToken(null);
        set({ token: null, userEmail: null, organization: null, workspace: null, product: null });
      },
    }),
    { name: "gruvle-reach-store" }
  )
);

/** True once the persisted store has rehydrated from localStorage. Any
 * auth-gated redirect must wait for this — otherwise a full page load
 * (direct nav, refresh) briefly sees token=null and bounces to /login
 * even though the user is signed in. */
export function useHasHydrated(): boolean {
  // Must start false unconditionally — this also runs during Next's
  // server-side render of the initial HTML, where `.persist` (and
  // localStorage) aren't available yet. Only useEffect (client-only)
  // may touch it.
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(useAppStore.persist?.hasHydrated() ?? true);
    const unsub = useAppStore.persist?.onFinishHydration(() => setHydrated(true));
    return unsub;
  }, []);

  return hydrated;
}
