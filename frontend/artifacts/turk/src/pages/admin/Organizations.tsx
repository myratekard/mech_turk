import { useEffect, useState } from "react";
import { Shell } from "@/components/layout/Shell";
import { api, Org } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { Building2, Plus, MailCheck, Search } from "lucide-react";

export default function Organizations() {
  const { toast } = useToast();
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [name, setName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");

  const load = () => api.listOrgs().then(setOrgs).catch(() => {});
  useEffect(() => { load(); }, []);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? orgs.filter(
        (o) => o.name.toLowerCase().includes(q) || o.id.toLowerCase().includes(q),
      )
    : orgs;

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const org = await api.createOrg(name.trim(), adminEmail.trim() || undefined);
      toast({
        title: "Organization created",
        description: org.emailSent
          ? `Clerk emailed an admin invite to ${adminEmail.trim()}.`
          : "Created. Add an admin email to send an invite.",
      });
      setName("");
      setAdminEmail("");
      await load();
    } catch (err: any) {
      toast({ title: "Failed", description: err?.message, variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-4xl mx-auto w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
            <Building2 className="text-primary" /> Organizations
          </h1>
          <p className="text-muted-foreground font-medium">
            Create an org in Clerk and invite its admin — Clerk sends the invitation email.
          </p>
        </div>

        <form onSubmit={create} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2 mb-6">
          <Input placeholder="Organization name" value={name} onChange={(e) => setName(e.target.value)} />
          <Input type="email" placeholder="Admin email (invite)" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} />
          <Button type="submit" disabled={busy} className="gap-1 shrink-0"><Plus size={16} /> Create</Button>
        </form>

        <div className="relative mb-4">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or ID…"
            className="pl-9"
          />
        </div>

        <div className="bg-card border border-border rounded-xl divide-y divide-border">
          {orgs.length === 0 ? (
            <p className="p-6 text-muted-foreground text-sm">No organizations yet.</p>
          ) : filtered.length === 0 ? (
            <p className="p-6 text-muted-foreground text-sm">No organizations match “{query}”.</p>
          ) : (
            filtered.map((o) => (
              <div key={o.id} className="p-4 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold">{o.name}</p>
                  <p className="text-xs text-muted-foreground font-mono truncate">{o.id}</p>
                </div>
                <span className="text-xs text-muted-foreground inline-flex items-center gap-1">
                  <MailCheck size={13} /> Clerk-managed
                </span>
              </div>
            ))
          )}
        </div>

        <p className="text-xs text-muted-foreground mt-4">
          Admins manage members, roles, and further invitations from the <b>Users</b> page (Clerk).
        </p>
      </div>
    </Shell>
  );
}
