import { useEffect, useState } from "react";
import { Shell } from "@/components/layout/Shell";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { Users as UsersIcon, ShieldPlus, MailCheck, Search } from "lucide-react";

// Org-admin: invite STAFF (always admin) by email — Clerk sends the email.
// Uploader users are NOT added here; they join via the org's referral link.
export default function Staff() {
  const { toast } = useToast();
  const [members, setMembers] = useState<{ email: string; name: string; role: string }[]>([]);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");

  const load = () => api.listStaff().then(setMembers).catch(() => {});
  useEffect(() => { load(); }, []);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? members.filter(
        (m) =>
          (m.name || "").toLowerCase().includes(q) ||
          m.email.toLowerCase().includes(q),
      )
    : members;

  const invite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setBusy(true);
    try {
      await api.inviteStaff(email.trim());
      toast({ title: "Staff invited", description: `Clerk emailed an admin invite to ${email.trim()}.` });
      setEmail("");
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
          <h1 id="tour-staff" className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
            <UsersIcon className="text-primary" /> Staff
          </h1>
          <p className="text-muted-foreground font-medium">
            Invite staff (admins) by email. Uploader users join via your referral link (Referrals).
          </p>
        </div>

        <form onSubmit={invite} className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-2 mb-6">
          <Input type="email" placeholder="Staff email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Button type="submit" disabled={busy} className="gap-1 shrink-0"><ShieldPlus size={16} /> Invite admin</Button>
        </form>
        <p className="text-xs text-muted-foreground mb-4 flex items-center gap-1">
          <MailCheck size={13} /> Staff join as <b>admin</b>.
        </p>

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
          {members.length === 0 ? (
            <p className="p-6 text-muted-foreground text-sm">No members yet.</p>
          ) : filtered.length === 0 ? (
            <p className="p-6 text-muted-foreground text-sm">No members match “{query}”.</p>
          ) : (
            filtered.map((m, i) => (
              <div key={i} className="p-4 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold truncate">{m.name || m.email}</p>
                  <p className="text-xs text-muted-foreground font-mono truncate">{m.email}</p>
                </div>
                <Badge variant="outline" className={`uppercase font-mono text-[10px] ${m.role === "admin" ? "text-amber-500" : "text-muted-foreground"}`}>{m.role}</Badge>
              </div>
            ))
          )}
        </div>
      </div>
    </Shell>
  );
}
