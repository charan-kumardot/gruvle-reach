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

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAppStore((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await api.post<{ access_token: string }>("/auth/login", { email, password });
      setAuth(access_token, email);
      router.push("/overview");
    } catch (err) {
      setError(err instanceof ApiError ? "Invalid email or password." : "Something went wrong. Is the API running?");
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
          <h1 className="text-lg font-semibold">Sign in to Gruvle Reach</h1>
        </div>
        <Card className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </div>
            {error && <p className="text-xs text-[var(--danger)]">{error}</p>}
            <Button type="submit" disabled={loading} className="mt-1">
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-xs text-[var(--muted-foreground)]">
          No account? <Link href="/register" className="text-[var(--accent)] hover:underline">Create one</Link>
        </p>
        <p className="mt-2 text-center text-xs text-[var(--muted-foreground)]">
          Demo login: <span className="font-mono">demo@gruvle-reach.io</span> / <span className="font-mono">demo12345</span>
        </p>
      </div>
    </div>
  );
}
