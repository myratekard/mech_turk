import { useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { Activity, ShieldCheck, UploadCloud, BarChart3, ArrowRight } from "lucide-react";

export default function Landing() {
  const [, setLocation] = useLocation();

  const features = [
    { icon: UploadCloud, title: "Upload Intel", desc: "Drop verified-account screenshots and let the AI extract the details." },
    { icon: ShieldCheck, title: "Verified Only", desc: "Every submission is checked for the official platform verified badge." },
    { icon: BarChart3, title: "Track & Earn", desc: "Accepted submissions earn points. Watch your stats climb." },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 md:px-10 py-5 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center text-primary-foreground shadow-[0_0_15px_rgba(0,255,255,0.4)]">
            <Activity size={20} strokeWidth={2.5} />
          </div>
          <span className="text-xl font-black uppercase tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">TURK</span>
        </div>
        <Button variant="outline" onClick={() => setLocation("/login")} className="font-bold uppercase tracking-wider">
          Sign In
        </Button>
      </header>

      {/* Hero */}
      <main className="flex-1">
        <section className="max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-primary text-xs font-bold uppercase tracking-wider mb-6">
            <ShieldCheck size={14} /> Verified-account intel platform
          </div>
          <h1 className="text-4xl md:text-6xl font-black uppercase tracking-tight leading-[1.05] mb-6">
            Collect, verify &amp; document<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">verified social accounts</span>
          </h1>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto mb-10">
            Upload profile screenshots — TURK confirms the official verified badge, extracts the profile,
            and routes the rest to a review queue. Built for teams running at scale.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button onClick={() => setLocation("/login")} className="font-bold uppercase tracking-wider gap-2 shadow-[0_0_15px_rgba(0,255,255,0.3)]">
              Enter Console <ArrowRight size={16} />
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-4">Access is invite-only. Have a registration link? Open it to create your account.</p>
        </section>

        {/* Features */}
        <section className="max-w-5xl mx-auto px-6 pb-24 grid grid-cols-1 md:grid-cols-3 gap-6">
          {features.map((f) => (
            <div key={f.title} className="bg-card border border-border rounded-xl p-6">
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary mb-4">
                <f.icon size={24} />
              </div>
              <h3 className="text-lg font-bold mb-2">{f.title}</h3>
              <p className="text-sm text-muted-foreground">{f.desc}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        TURK · Verified-Account Artifact Extractor
      </footer>
    </div>
  );
}
