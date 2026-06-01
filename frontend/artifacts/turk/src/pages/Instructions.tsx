import { Shell } from "@/components/layout/Shell";
import { Link } from "wouter";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger, DialogTitle } from "@/components/ui/dialog";
import { PROFILE_SCREENS, ScreenFrame } from "@/components/PhoneMockups";
import {
  UploadCloud,
  Clock,
  CheckCircle2,
  XCircle,
  Zap,
  Trophy,
  AlertTriangle,
  Image,
  FileCheck,
  Ban,
  ArrowRight,
  Smartphone,
  Maximize2,
  ShieldCheck,
} from "lucide-react";

const steps = [
  {
    number: "01",
    icon: ShieldCheck,
    title: "Find a verified creator",
    color: "text-primary",
    bg: "bg-primary/10",
    border: "border-primary/20",
    description:
      "On Instagram, X (Twitter) or TikTok, find a creator of African descent who has the official verified badge next to their name. That badge is what we're collecting.",
  },
  {
    number: "02",
    icon: Smartphone,
    title: "Screenshot it on your phone",
    color: "text-secondary",
    bg: "bg-secondary/10",
    border: "border-secondary/20",
    description:
      "Open their profile in the app and take a screenshot showing the display name, @handle and the verified badge — full and uncropped. One profile per screenshot.",
  },
  {
    number: "03",
    icon: UploadCloud,
    title: "Upload it and earn",
    color: "text-green-500",
    bg: "bg-green-500/10",
    border: "border-green-500/20",
    description:
      "Upload the screenshot on the Upload page. Each new verified account earns you 50 points — watch your total climb on your dashboard.",
  },
];

const rules = [
  {
    icon: Image,
    label: "Screenshots must be real",
    detail: "Do not submit edited, cropped, or AI-generated images. Manipulated screenshots will be rejected and repeated violations result in account removal.",
  },
  {
    icon: FileCheck,
    label: "Content must be fully visible",
    detail: "Usernames, metrics (likes, views, shares), and timestamps must all be clearly visible and uncropped in the frame.",
  },
  {
    icon: Ban,
    label: "Avoid duplicates",
    detail: "Each account should only be captured once. Try to avoid uploading duplicates or re-uploading the same image — they don't earn points and can cost you points.",
  },
  {
    icon: AlertTriangle,
    label: "No inappropriate content",
    detail: "Screenshots containing violent, explicit, or otherwise inappropriate content will be permanently rejected.",
  },
];

const pointTiers = [
  { label: "Approved verified account", range: "+50 pts", color: "text-green-500" },
  { label: "Duplicate (account already captured)", range: "−5 pts", color: "text-red-500" },
  { label: "Re-uploading the same image", range: "warning, then up to −10 pts", color: "text-red-500" },
  { label: "Invalid / unsupported", range: "0 pts", color: "text-muted-foreground" },
];

export default function Instructions() {
  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-4xl mx-auto w-full">
        <div id="tour-how-it-works" className="mb-10">
          <h1 className="text-3xl font-black uppercase tracking-tight mb-2">What To Do</h1>
          <p className="text-muted-foreground font-medium leading-relaxed">
            TURK is building a directory of <span className="text-foreground font-semibold">verified social
            accounts of African-descent creators</span>. Your task is simple: find a verified creator on
            Instagram, X or TikTok, screenshot their profile on your phone, and upload it here — you earn
            points for every new verified account you add.
          </p>
        </div>

        {/* Mobile screenshots + examples */}
        <section className="mb-12">
          <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-6">
            Upload Mobile Screenshots
          </h2>
          <div className="bg-card border border-primary/20 rounded-xl p-6 mb-6 flex gap-5 items-start">
            <div className="w-11 h-11 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <Smartphone size={22} className="text-primary" />
            </div>
            <div>
              <h3 className="font-bold text-base uppercase tracking-wide text-primary mb-1.5">
                Take it on your phone
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Upload <span className="text-foreground font-semibold">screenshots taken on your mobile phone</span> of
                the full profile page — the display name, @handle and the official verified badge must all be visible and
                uncropped. We're building a directory of <span className="text-foreground font-semibold">verified
                accounts of African-descent creators</span>, so please submit those. Desktop or web captures, photos of a
                screen, and edited or cropped images are not accepted.
              </p>
            </div>
          </div>

          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-3">
            Examples — tap to enlarge
          </p>
          <div className="flex flex-wrap justify-center gap-4 sm:gap-6">
            {PROFILE_SCREENS.map(({ platform, Screen }) => (
              <Dialog key={platform}>
                <DialogTrigger asChild>
                  <button
                    className="group flex flex-col items-center gap-2 focus:outline-none"
                    aria-label={`View ${platform} example screenshot`}
                  >
                    <div className="relative group-hover:scale-[1.03] transition-transform">
                      <ScreenFrame width={150}>
                        <Screen />
                      </ScreenFrame>
                      <div className="absolute inset-0 rounded-3xl bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                        <Maximize2 size={20} className="text-white" />
                      </div>
                    </div>
                    <span className="text-[10px] sm:text-xs font-bold uppercase tracking-widest text-muted-foreground">
                      {platform}
                    </span>
                  </button>
                </DialogTrigger>
                <DialogContent className="w-auto max-w-none flex flex-col items-center gap-3">
                  <DialogTitle className="text-sm uppercase tracking-wide">
                    {platform} — example profile
                  </DialogTitle>
                  <ScreenFrame width={300}>
                    <Screen />
                  </ScreenFrame>
                </DialogContent>
              </Dialog>
            ))}
          </div>
        </section>

        {/* Steps */}
        <section className="mb-12">
          <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-6">
            Your 3 Steps
          </h2>
          <div className="space-y-4">
            {steps.map((step) => (
              <div
                key={step.number}
                className={`bg-card border ${step.border} rounded-xl p-6 flex gap-5 items-start`}
              >
                <div className={`w-11 h-11 rounded-lg ${step.bg} flex items-center justify-center shrink-0`}>
                  <step.icon size={22} className={step.color} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1.5">
                    <span className="text-xs font-black font-mono text-muted-foreground/50 tracking-widest">
                      {step.number}
                    </span>
                    <h3 className={`font-bold text-base uppercase tracking-wide ${step.color}`}>
                      {step.title}
                    </h3>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Rules */}
        <section className="mb-12">
          <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-6">
            Submission Rules
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {rules.map((rule) => (
              <div key={rule.label} className="bg-card border border-border rounded-xl p-5 flex gap-4 items-start">
                <div className="w-9 h-9 rounded-md bg-muted flex items-center justify-center shrink-0 text-muted-foreground">
                  <rule.icon size={18} />
                </div>
                <div>
                  <p className="font-bold text-sm mb-1">{rule.label}</p>
                  <p className="text-xs text-muted-foreground leading-relaxed">{rule.detail}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 bg-destructive/5 border border-destructive/20 rounded-xl p-5 flex gap-4 items-start">
            <div className="w-9 h-9 rounded-md bg-destructive/10 flex items-center justify-center shrink-0 text-destructive">
              <XCircle size={18} />
            </div>
            <div>
              <p className="font-bold text-sm text-destructive mb-1">Invalid uploads don't count</p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Submissions that aren't a verified account show up in your dashboard under Invalid. Too many of them can affect your account.
              </p>
            </div>
          </div>
        </section>

        {/* Points */}
        <section className="mb-12">
          <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-6">
            Points & Earnings
          </h2>
          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <div className="p-5 border-b border-border flex items-center gap-3">
              <Zap size={18} className="text-primary" />
              <p className="font-bold text-sm uppercase tracking-wide">Points per Submission</p>
            </div>
            <div className="divide-y divide-border">
              {pointTiers.map((tier) => (
                <div key={tier.label} className="px-5 py-4 flex items-center justify-between">
                  <span className="text-sm font-semibold text-muted-foreground">{tier.label}</span>
                  <span className={`font-black font-mono text-base ${tier.color}`}>{tier.range}</span>
                </div>
              ))}
            </div>
            <div className="p-5 border-t border-border bg-muted/20">
              <p className="text-xs text-muted-foreground leading-relaxed">
                Points are awarded automatically once a submission is accepted. Capturing an account that's
                already in the directory costs a few points, and the penalty for re-uploading your own image
                grows if you keep doing it — so focus on fresh, verified accounts. Your total accumulates on
                the dashboard and goes toward your position on the leaderboard.
              </p>
            </div>
          </div>
        </section>

        {/* Leaderboard note */}
        <section className="mb-12">
          <div className="bg-card border border-secondary/20 rounded-xl p-6 flex gap-5 items-start">
            <div className="w-11 h-11 rounded-lg bg-secondary/10 flex items-center justify-center shrink-0">
              <Trophy size={22} className="text-secondary" />
            </div>
            <div>
              <h3 className="font-bold text-base uppercase tracking-wide text-secondary mb-1.5">
                Leaderboard
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Your total points place you on the leaderboard. The more you earn, the higher you rank.
                Keep your acceptance rate up to stay near the top.
              </p>
            </div>
          </div>
        </section>

        {/* CTA */}
        <div className="flex gap-4">
          <Link href="/upload">
            <Button className="gap-2 font-bold uppercase tracking-wide bg-primary text-primary-foreground hover:bg-primary/90 shadow-[0_0_15px_rgba(0,255,255,0.3)]">
              <UploadCloud size={16} />
              Start Uploading
              <ArrowRight size={14} />
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button variant="outline" className="font-bold uppercase tracking-wide border-border hover:bg-muted">
              View Dashboard
            </Button>
          </Link>
        </div>
      </div>
    </Shell>
  );
}
