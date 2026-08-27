"use client";

import { useEffect, useState } from "react";
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
    if (orgs && orgs.length > 0 && !organization) setOrganization(orgs[0]);
  }, [orgs, organization, setOrganization]);

  const { data: workspaces } = useQuery({
    queryKey: ["workspaces", organization?.id],
    queryFn: () => api.get<Workspace[]>(`/organizations/${organization!.id}/workspaces`),
    enabled: !!token && !!organization,
  });

  useEffect(() => {
    if (workspaces && workspaces.length > 0 && !workspace) setWorkspace(workspaces[0]);
  }, [workspaces, workspace, setWorkspace]);

  const { data: products, isFetched: productsFetched } = useQuery({
    queryKey: ["products", workspace?.id],
    queryFn: () => api.get<Product[]>(`/workspaces/${workspace!.id}/products`),
    enabled: !!token && !!workspace,
  });

  useEffect(() => {
    if (products && products.length > 0 && !product) setProduct(products[0]);
    if (productsFetched) setReady(true);
  }, [products, productsFetched, product, setProduct]);

  return { organization, workspace, product, products: products ?? [], ready };
}
