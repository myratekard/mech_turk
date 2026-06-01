import { useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { Activity, ShieldCheck, UploadCloud, BarChart3, ArrowRight } from "lucide-react";
import { PhoneMockups } from "@/components/PhoneMockups";

export default function Landing() {
  const [, setLocation] = useLocation();

  const features = [
    { icon: ShieldCheck, title: "Verified creators", desc: "We collect accounts carrying the official verified badge — blue, gold or grey — belonging to creators of African descent." },
    { icon: UploadCloud, title: "Snap & upload", desc: "Screenshot a verified profile on your phone and drop it in. Each one is checked and added in seconds." },
    { icon: BarChart3, title: "Earn & track", desc: "Every new verified account you add earns points. Watch your total climb on your dashboard and the leaderboard." },
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
        <section className="max-w-4xl mx-auto px-6 pt-20 pb-4 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/50 border border-border mb-6 backdrop-blur-sm">
            <span className="flex h-2 w-2 rounded-full bg-primary shadow-[0_0_8px_rgba(0,255,255,0.8)] animate-pulse"></span>
            <span className="text-xs font-mono font-medium text-muted-foreground uppercase tracking-wider">Now open</span>
          </div>
          <h1 className="text-4xl md:text-6xl font-black uppercase tracking-tight leading-[1.05] mb-6">
            Spot it. Screenshot it.<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">Earn.</span>
          </h1>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto mb-4 leading-relaxed">
            TURK is a community directory of <span className="text-foreground font-semibold">verified social
            accounts of African-descent creators</span>. Find a verified creator on Instagram, X or TikTok,
            screenshot their profile on your phone, and upload it.
          </p>
          <p className="text-muted-foreground text-sm max-w-2xl mx-auto mb-10">
            You earn points for every verified account you contribute — no fakes, no duplicates, just real verified profiles.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button onClick={() => setLocation("/login")} className="font-bold uppercase tracking-wider gap-2 shadow-[0_0_15px_rgba(0,255,255,0.3)]">
              Start Earning <ArrowRight size={16} />
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-4">Access is invite-only. Have a registration link? Open it to create your account.</p>
        </section>

        {/* Supported platforms — Instagram / X / TikTok mockups */}
        <PhoneMockups />

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
        TURK · Upload verified accounts. Earn.
      </footer>
    </div>
  );
}
