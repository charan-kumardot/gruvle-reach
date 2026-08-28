"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Eye, Plus } from "lucide-react";
import { api } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Website } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { ConnectWebsiteDialog } from "@/components/app/visibility/connect-website-dialog";
import { OverviewTab } from "@/components/app/visibility/overview-tab";
import { SEOTab } from "@/components/app/visibility/seo-tab";
import { GEOTab } from "@/components/app/visibility/geo-tab";
import { OpportunitiesTab } from "@/components/app/visibility/opportunities-tab";
import { ChangesTab } from "@/components/app/visibility/changes-tab";
import { SettingsTab } from "@/components/app/visibility/settings-tab";

export default function VisibilityPage() {
  const { workspace, product } = useAppStore();
  const [connectOpen, setConnectOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string>("");

  const { data: websites } = useQuery({
    queryKey: ["websites", workspace?.id, product?.id],
    queryFn: () => api.get<Website[]>(`/workspaces/${workspace!.id}/websites?product_id=${product!.id}`),
    enabled: !!workspace && !!product,
  });

  if (!product) {
    return <EmptyState icon={Eye} title="Select a product" description="Choose a product to manage its website visibility." />;
  }

  const selected = websites?.find((w) => w.id === selectedId) ?? websites?.[0];

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Visibility"
        description="Help your product get discovered by humans and AI — while preserving its meaning, brand, and design."
        action={
          <Button size="sm" onClick={() => setConnectOpen(true)}>
            <Plus className="mr-1.5 h-4 w-4" /> Add website
          </Button>
        }
      />

      {websites && websites.length > 0 ? (
        <>
          {websites.length > 1 && (
            <div className="mb-4">
              <Select value={selected?.id} onValueChange={setSelectedId}>
                <SelectTrigger className="w-64"><SelectValue placeholder="Select a website" /></SelectTrigger>
                <SelectContent>
                  {websites.map((w) => <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}

          {selected && (
            <Tabs defaultValue="overview">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="seo">SEO</TabsTrigger>
                <TabsTrigger value="geo">GEO / AI Visibility</TabsTrigger>
                <TabsTrigger value="opportunities">Opportunities</TabsTrigger>
                <TabsTrigger value="changes">Website Changes</TabsTrigger>
                <TabsTrigger value="settings">Settings</TabsTrigger>
              </TabsList>
              <TabsContent value="overview"><OverviewTab website={selected} /></TabsContent>
              <TabsContent value="seo"><SEOTab website={selected} /></TabsContent>
              <TabsContent value="geo"><GEOTab website={selected} /></TabsContent>
              <TabsContent value="opportunities"><OpportunitiesTab website={selected} /></TabsContent>
              <TabsContent value="changes"><ChangesTab website={selected} /></TabsContent>
              <TabsContent value="settings"><SettingsTab website={selected} /></TabsContent>
            </Tabs>
          )}
        </>
      ) : (
        <EmptyState
          icon={Eye}
          title="No website connected yet"
          description="Connect a website and its GitHub repository — Reach will scan it, find opportunities, and prepare pull requests for you to review."
          action={<Button size="sm" onClick={() => setConnectOpen(true)}>Add website</Button>}
        />
      )}

      <ConnectWebsiteDialog open={connectOpen} onOpenChange={setConnectOpen} onConnected={(w) => setSelectedId(w.id)} />
    </div>
  );
}
