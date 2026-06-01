import { useEffect, useState } from "react";
import { Shell } from "@/components/layout/Shell";
import { api, User } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { ShieldCheck, MailCheck, UserPlus } from "lucide-react";

// Superuser-only: invite platform reviewers/admins (turk admins), not tied to any org.
export default function TurkAdmins() {
  const { toast } = useToast();
  const [admins, setAdmins] = useState<User[]>([]);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.listTurkAdmins().then(setAdmins).catch(() => {});
  useEffect(() => { load(); }, []);

  const invite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setBusy(true);
    try {
      await api.inviteTurkAdmin(email.trim());
      toast({ title: "Turk admin invited", description: `Clerk emailed an invite to ${email.trim()}.` });
      setEmail("");
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
          <h1 id="tour-turk-admins" className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
            <ShieldCheck className="text-primary" /> Turk Admins
          </h1>
          <p className="text-muted-foreground font-medium">
            Platform reviewers — they can review the queue and see platform analytics. Not part of any org.
          </p>
        </div>

        <form onSubmit={invite} className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-2 mb-6">
          <Input type="email" placeholder="Reviewer email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Button type="submit" disabled={busy} className="gap-1 shrink-0"><UserPlus size={16} /> Invite turk admin</Button>
        </form>
        <p className="text-xs text-muted-foreground mb-4 flex items-center gap-1">
          <MailCheck size={13} /> They become a turk admin when they accept and sign up with this email.
        </p>

        <div className="bg-card border border-border rounded-xl divide-y divide-border">
          {admins.length === 0 ? (
            <p className="p-6 text-muted-foreground text-sm">No turk admins yet.</p>
          ) : (
            admins.map((u) => (
              <div key={u.id} className="p-4 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold truncate">{u.username}</p>
                  <p className="text-xs text-muted-foreground font-mono truncate">{u.email || "—"}</p>
                </div>
                <span className="text-xs text-amber-500 font-mono uppercase">turk admin</span>
              </div>
            ))
          )}
        </div>
      </div>
    </Shell>
  );
}
