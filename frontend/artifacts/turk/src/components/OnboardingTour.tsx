import { useState, useEffect } from "react";
import { useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ShieldCheck, Smartphone, UploadCloud, Trophy, ArrowRight, X } from "lucide-react";

const STORAGE_KEY = "turk_onboarding_done";

const steps = [
  {
    icon: ShieldCheck,
    color: "text-primary",
    bg: "bg-primary/10",
    glow: "shadow-[0_0_30px_rgba(0,255,255,0.15)]",
    subtitle: "30-second tour",
    title: "Welcome to TURK",
    description:
      "TURK is a directory of verified social accounts of African-descent creators. Your job is simple: find a verified creator, screenshot their profile, and earn points for every one you add.",
  },
  {
    icon: ShieldCheck,
    color: "text-primary",
    bg: "bg-primary/10",
    glow: "shadow-[0_0_30px_rgba(0,255,255,0.15)]",
    subtitle: "Step 1",
    title: "Find a verified creator",
    description:
      "On Instagram, X (Twitter) or TikTok, find a creator of African descent who has the official verified badge next to their name — blue, or gold/grey on X.",
  },
  {
    icon: Smartphone,
    color: "text-secondary",
    bg: "bg-secondary/10",
    glow: "shadow-[0_0_30px_rgba(167,139,250,0.15)]",
    subtitle: "Step 2",
    title: "Screenshot it on your phone",
    description:
      "Open their profile in the app and take a screenshot showing the display name, @handle and the verified badge — full and uncropped. One profile per screenshot.",
  },
  {
    icon: UploadCloud,
    color: "text-green-500",
    bg: "bg-green-500/10",
    glow: "shadow-[0_0_30px_rgba(34,197,94,0.15)]",
    subtitle: "Step 3",
    title: "Upload it and earn",
    description:
      "Upload the screenshot on the Upload page. Each new verified account earns you 50 points — watch your total grow on your dashboard.",
  },
  {
    icon: Trophy,
    color: "text-secondary",
    bg: "bg-secondary/10",
    glow: "shadow-[0_0_30px_rgba(167,139,250,0.15)]",
    subtitle: "You're set!",
    title: "A few things to avoid",
    description:
      "Only real, uncropped screenshots count. Re-uploading the same image, or an account that's already been added, loses points — so look for fresh verified creators.",
  },
];

export function OnboardingTour() {
  const [, navigate] = useLocation();
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(false);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(STORAGE_KEY)) setVisible(true);
  }, []);

  const dismiss = (goTo = "/upload") => {
    setExiting(true);
    localStorage.setItem(STORAGE_KEY, "1");
    setTimeout(() => {
      setVisible(false);
      navigate(goTo);
    }, 280);
  };

  if (!visible) return null;

  const current = steps[step];
  const isFirst = step === 0;
  const isLast = step === steps.length - 1;
  const Icon = current.icon;

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-300 bg-background/80 backdrop-blur-sm",
        exiting ? "opacity-0" : "opacity-100",
      )}
    >
      <div
        className={cn(
          "relative w-full max-w-md bg-card border border-border rounded-2xl overflow-hidden transition-all duration-300",
          exiting ? "scale-95 opacity-0" : "scale-100 opacity-100",
        )}
      >
        <div className="h-0.5 bg-muted w-full">
          <div className="h-full bg-primary transition-all duration-500" style={{ width: `${((step + 1) / steps.length) * 100}%` }} />
        </div>

        <button
          onClick={() => dismiss()}
          className="absolute top-4 right-4 p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          aria-label="Skip tour"
        >
          <X size={16} />
        </button>

        <div className="px-8 pt-10 pb-8">
          <div className={cn("w-16 h-16 rounded-2xl flex items-center justify-center mb-6 mx-auto", current.bg, current.glow)}>
            <Icon size={32} className={current.color} />
          </div>

          <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground text-center mb-2">{current.subtitle}</p>
          <h2 className="text-2xl font-black uppercase tracking-tight text-center mb-4">{current.title}</h2>
          <p className="text-sm text-muted-foreground leading-relaxed text-center">{current.description}</p>

          <div className="flex justify-center gap-1.5 mt-8 mb-6">
            {steps.map((_, i) => (
              <button
                key={i}
                onClick={() => setStep(i)}
                className={cn("rounded-full transition-all duration-200", i === step ? "w-5 h-1.5 bg-primary" : "w-1.5 h-1.5 bg-muted-foreground/30 hover:bg-muted-foreground/60")}
                aria-label={`Go to step ${i + 1}`}
              />
            ))}
          </div>

          <div className="flex gap-3">
            {!isFirst && (
              <Button variant="outline" className="flex-1 border-border font-bold uppercase tracking-wider" onClick={() => setStep((s) => s - 1)}>
                Back
              </Button>
            )}
            {isLast ? (
              <Button className="flex-1 bg-primary text-primary-foreground font-bold uppercase tracking-wider hover:bg-primary/90 shadow-[0_0_20px_rgba(0,255,255,0.3)] gap-2" onClick={() => dismiss("/upload")}>
                Start uploading <ArrowRight size={16} />
              </Button>
            ) : (
              <Button className="flex-1 bg-primary text-primary-foreground font-bold uppercase tracking-wider hover:bg-primary/90 gap-2" onClick={() => setStep((s) => s + 1)}>
                Next <ArrowRight size={16} />
              </Button>
            )}
          </div>

          <button onClick={() => dismiss()} className="block w-full text-center mt-4 text-xs text-muted-foreground hover:text-foreground transition-colors">
            Skip tour
          </button>
        </div>
      </div>
    </div>
  );
}
