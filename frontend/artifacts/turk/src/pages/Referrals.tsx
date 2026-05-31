import { useEffect, useState } from "react";
import { Shell } from "@/components/layout/Shell";
import { api, User, registrationLink } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { GitBranch, Copy } from "lucide-react";

export default function Referrals() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [referrals, setReferrals] = useState<User[]>([]);

  useEffect(() => { api.myReferrals().then(setReferrals).catch(() => {}); }, []);

  const copy = (t: string) => { navigator.clipboard.writeText(t); toast({ title: "Copied" }); };
  const link = user ? registrationLink(user.referralCode) : "";

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-3xl mx-auto w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
            <GitBranch className="text-primary" /> Referrals
          </h1>
          <p className="text-muted-foreground font-medium">Share your link — everyone who joins through it shows up here.</p>
        </div>

        <div className="bg-card border border-border rounded-xl p-5 mb-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-bold">Your invite link</p>
            <span className="text-xs text-muted-foreground font-mono">code: {user?.referralCode}</span>
          </div>
          {user?.orgId == null ? (
            <p className="text-sm text-muted-foreground">Join or run an organization to invite users.</p>
          ) : (
            <div className="flex gap-2">
              <Input readOnly value={link} className="font-mono text-xs" />
              <Button variant="outline" className="gap-1 shrink-0" onClick={() => copy(link)}><Copy size={14} /> Copy</Button>
            </div>
          )}
        </div>

        <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground mb-3">
          Your users ({referrals.length})
        </h2>
        <div className="bg-card border border-border rounded-xl divide-y divide-border">
          {referrals.length === 0 ? (
            <p className="p-6 text-muted-foreground text-sm">No referrals yet. Share your link to start.</p>
          ) : (
            referrals.map((u) => (
              <div key={u.id} className="p-4 flex items-center justify-between">
                <p className="font-semibold">{u.username}</p>
                <span className="text-xs text-muted-foreground font-mono uppercase">{u.role}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </Shell>
  );
}
