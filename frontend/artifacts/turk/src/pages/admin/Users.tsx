import { useEffect, useState } from "react";
import { Shell } from "@/components/layout/Shell";
import { api, User } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { Users as UsersIcon, Ban, ShieldCheck, Search } from "lucide-react";

// Superuser-only: moderate (block/unblock) any provisioned user across the platform.
export default function Users() {
  const { user: me } = useAuth();
  const { toast } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");

  const load = () => api.listUsers().then(setUsers).catch(() => {});
  useEffect(() => { load(); }, []);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? users.filter(
        (u) =>
          u.username.toLowerCase().includes(q) ||
          (u.email || "").toLowerCase().includes(q),
      )
    : users;

  const run = async (fn: () => Promise<any>, label: string) => {
    setBusy(true);
    try { await fn(); await load(); toast({ title: label }); }
    catch (e: any) { toast({ title: "Failed", description: e?.message, variant: "destructive" }); }
    finally { setBusy(false); }
  };

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-4xl mx-auto w-full">
        <div className="mb-8">
          <h1 id="tour-users" className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
            <UsersIcon className="text-primary" /> Users
          </h1>
          <p className="text-muted-foreground font-medium">Moderate any account on the platform.</p>
        </div>

        <div className="relative mb-4">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or email…"
            className="pl-9"
          />
        </div>

        <div className="bg-card border border-border rounded-xl divide-y divide-border">
          {users.length === 0 ? (
            <p className="p-6 text-muted-foreground text-sm">No users yet.</p>
          ) : filtered.length === 0 ? (
            <p className="p-6 text-muted-foreground text-sm">No users match “{query}”.</p>
          ) : (
            filtered.map((u) => {
              const canBlock = u.id !== me?.id && u.role !== "superuser";
              return (
                <div key={u.id} className="p-4 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-semibold truncate">{u.username}</p>
                      {u.blocked && <Badge variant="outline" className="text-[10px] uppercase font-mono text-red-500 border-red-500/30">Blocked</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground font-mono truncate">
                      {u.email || "—"}{u.referredBy ? ` · invited by #${u.referredBy}` : ""}
                    </p>
                  </div>
                  {canBlock && (
                    u.blocked ? (
                      <Button size="sm" variant="outline" disabled={busy} className="gap-1"
                        onClick={() => run(() => api.unblockUser(u.id), "User unblocked")}>
                        <ShieldCheck size={14} /> Unblock
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" disabled={busy}
                        className="gap-1 border-destructive/40 text-destructive hover:bg-destructive/10"
                        onClick={() => run(() => api.blockUser(u.id), "User blocked")}>
                        <Ban size={14} /> Block
                      </Button>
                    )
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </Shell>
  );
}
