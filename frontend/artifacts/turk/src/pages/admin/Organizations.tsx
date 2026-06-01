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
  const [attempted, setAttempted] = useState(false);

  const load = () => api.listOrgs().then(setOrgs).catch(() => {});
  useEffect(() => { load(); }, []);

  const nameOk = !!name.trim();
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(adminEmail.trim());
  const nameErr = attempted && !nameOk;
  const emailErr = attempted && !emailOk;

  const q = query.trim().toLowerCase();
  const filtered = q
    ? orgs.filter(
        (o) => o.name.toLowerCase().includes(q) || o.id.toLowerCase().includes(q),
      )
    : orgs;

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setAttempted(true);
    if (!nameOk || !emailOk) {
      toast({ title: "Fill in both fields", description: "Organization name and a valid admin email are required.", variant: "destructive" });
      return;
    }
    setBusy(true);
    try {
      const org = await api.createOrg(name.trim(), adminEmail.trim());
      toast({
        title: "Organization created",
        description: org.emailSent
          ? `Clerk emailed an admin invite to ${adminEmail.trim()}.`
          : "Created.",
      });
      setName("");
      setAdminEmail("");
      setAttempted(false);
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
          <h1 id="tour-orgs" className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
            <Building2 className="text-primary" /> Organizations
          </h1>
          <p className="text-muted-foreground font-medium">
            Create an org in Clerk and invite its admin — Clerk sends the invitation email.
          </p>
        </div>

        <form onSubmit={create} className="bg-card border border-primary/20 rounded-xl p-5 mb-6 shadow-[inset_0_0_30px_rgba(0,255,255,0.03)]">
          <p className="text-xs font-bold uppercase tracking-widest text-primary mb-4">New organization</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="org-name" className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5">
                Organization name <span className="text-destructive">*</span>
              </label>
              <Input
                id="org-name"
                placeholder="e.g. Acme Media"
                value={name}
                onChange={(e) => setName(e.target.value)}
                aria-invalid={nameErr}
                className={nameErr ? "border-destructive ring-1 ring-destructive focus-visible:ring-destructive" : ""}
              />
              {nameErr && <p className="text-xs text-destructive mt-1">Enter an organization name.</p>}
            </div>
            <div>
              <label htmlFor="org-admin-email" className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5">
                Admin email <span className="text-destructive">*</span>
              </label>
              <Input
                id="org-admin-email"
                type="email"
                placeholder="admin@company.com"
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                aria-invalid={emailErr}
                className={emailErr ? "border-destructive ring-1 ring-destructive focus-visible:ring-destructive" : ""}
              />
              {emailErr && <p className="text-xs text-destructive mt-1">Enter a valid admin email — Clerk sends the invite here.</p>}
            </div>
          </div>
          <div className="flex items-center justify-between gap-3 mt-4">
            <p className="text-xs text-muted-foreground">Both fields are required — Clerk emails the admin an invite.</p>
            <Button type="submit" disabled={busy} className="gap-1 shrink-0"><Plus size={16} /> Create</Button>
          </div>
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
