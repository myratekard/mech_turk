import { useEffect, useState } from "react";
import { SignUp } from "@clerk/react";
import { api, RefInfo } from "@/lib/api";
import { Activity } from "lucide-react";

export default function Register() {
  // Capture a referral/org code so the post-signup sync can attribute the account.
  const ref = new URLSearchParams(window.location.search).get("ref") || "";
  const [info, setInfo] = useState<RefInfo | null>(null);

  useEffect(() => {
    if (ref) {
      localStorage.setItem("turk_ref", ref);
      api.refInfo(ref).then(setInfo).catch(() => setInfo({ valid: false }));
    }
  }, [ref]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background p-4 gap-6">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-md bg-primary flex items-center justify-center text-primary-foreground shadow-[0_0_15px_rgba(0,255,255,0.4)]">
          <Activity size={22} strokeWidth={2.5} />
        </div>
        <span className="text-2xl font-black uppercase tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">TURK</span>
      </div>
      {ref && info?.valid && (
        <p className="text-sm text-muted-foreground -mb-2">
          Joining <span className="text-foreground font-semibold">{info.orgName || "your organization"}</span>
          {" "}as <span className="uppercase text-primary font-bold">{info.role}</span>
        </p>
      )}
      <SignUp routing="hash" signInUrl={ref ? `/login?ref=${encodeURIComponent(ref)}` : "/login"} forceRedirectUrl="/dashboard" />
    </div>
  );
}
