"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Radar } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAppStore((s) => s.setAuth);
  const [form, setForm] = useState({ organization_name: "", full_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await api.post<{ access_token: string }>("/auth/register", form);
      setAuth(access_token, form.email);
      router.push("/overview");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] bg-[var(--accent)] text-[var(--accent-foreground)]">
            <Radar className="h-5 w-5" />
          </div>
          <h1 className="text-lg font-semibold">Build your growth map</h1>
        </div>
        <Card className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="org">Organization name</Label>
              <Input id="org" required value={form.organization_name} onChange={(e) => setForm({ ...form, organization_name: e.target.value })} placeholder="Gruvle" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="name">Your name</Label>
              <Input id="name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Jordan Founder" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@company.com" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="At least 8 characters" />
            </div>
            {error && <p className="text-xs text-[var(--danger)]">{error}</p>}
            <Button type="submit" disabled={loading} className="mt-1">
              {loading ? "Creating account…" : "Create account"}
            </Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-xs text-[var(--muted-foreground)]">
          Already have an account? <Link href="/login" className="text-[var(--accent)] hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
