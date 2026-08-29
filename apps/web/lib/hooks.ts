"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api-client";
import { useAppStore } from "./store";
import type { Organization, Product, Workspace } from "./types";

/** Bootstraps the current user's org/workspace/product context after login.
 * Picks the first organization and workspace (multi-org switching is a
 * natural extension point — the data model already supports it). */
export function useBootstrap() {
  const { token, organization, workspace, product, setOrganization, setWorkspace, setProduct } = useAppStore();
  const [ready, setReady] = useState(false);

  const { data: orgs } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api.get<Organization[]>("/organizations"),
    enabled: !!token,
  });

  useEffect(() => {
    if (!orgs || orgs.length === 0) return;
    // A persisted organization (from localStorage) can go stale — deleted,
    // or this user no longer a member. Re-validate against the live list
    // on every load rather than trusting the cache just because it's set.
    if (organization && orgs.some((o) => o.id === organization.id)) return;
    setOrganization(orgs[0]);
  }, [orgs, organization, setOrganization]);

  const { data: workspaces } = useQuery({
    queryKey: ["workspaces", organization?.id],
    queryFn: () => api.get<Workspace[]>(`/organizations/${organization!.id}/workspaces`),
    enabled: !!token && !!organization,
  });

  useEffect(() => {
    if (!workspaces || workspaces.length === 0) return;
    if (workspace && workspaces.some((w) => w.id === workspace.id)) return;
    setWorkspace(workspaces[0]);
  }, [workspaces, workspace, setWorkspace]);

  const { data: products, isFetched: productsFetched } = useQuery({
    queryKey: ["products", workspace?.id],
    queryFn: () => api.get<Product[]>(`/workspaces/${workspace!.id}/products`),
    enabled: !!token && !!workspace,
  });

  useEffect(() => {
    if (products && products.length > 0 && !(product && products.some((p) => p.id === product.id))) {
      setProduct(products[0]);
    }
    if (productsFetched) setReady(true);
  }, [products, productsFetched, product, setProduct]);

  return { organization, workspace, product, products: products ?? [], ready };
}

/** Discovery/scan endpoints now return immediately and do the real work in
 * a background thread (see app/core/background.py — a synchronous version
 * used to time out on Render's free tier once queries got broad enough).
 * There's no synchronous result to show, so poll the relevant list query
 * for a bit after starting so results appear without a manual refresh. */
export function usePollAfterAction(invalidate: () => void, durationMs = 75_000) {
  const [polling, setPolling] = useState(false);
  const invalidateRef = useRef(invalidate);
  invalidateRef.current = invalidate;

  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(() => invalidateRef.current(), 5000);
    const timeout = setTimeout(() => setPolling(false), durationMs);
    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [polling, durationMs]);

  return { polling, start: () => setPolling(true) };
}
