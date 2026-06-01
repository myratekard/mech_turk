import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { ArrowRight, ArrowLeft, X } from "lucide-react";
import { useAuth } from "@/lib/auth";

// Per-user keys: signing into a different account on the same browser gets its own tour
// state, so a fresh account always sees the walkthrough.
const doneKey = (id: string | number) => `turk_tour_done:${id}`;
const stepKey = (id: string | number) => `turk_tour_step:${id}`;

interface Step {
  page: string;
  targetId: string;
  title: string;
  description: string;
  tip?: "bottom" | "top";
}

// Steps everyone sees — these pages exist for every role.
const COMMON: Step[] = [
  {
    page: "/instructions",
    targetId: "tour-how-it-works",
    title: "Start Here",
    description: "This page walks you through the full submission process — read it once and you'll know everything you need to start earning.",
    tip: "bottom",
  },
  {
    page: "/dashboard",
    targetId: "tour-stats-grid",
    title: "Your Stats",
    description: "Track your total points, accepted submissions, in-review count, and invalid uploads — all updated in real time after every submission.",
    tip: "bottom",
  },
  {
    page: "/upload",
    targetId: "tour-dropzone",
    title: "Upload Screenshots",
    description: "Drag & drop or tap here to select one or more screenshots. Each file uploads individually so you can monitor progress per image.",
    tip: "bottom",
  },
  {
    page: "/submissions",
    targetId: "tour-submissions-list",
    title: "Your Submission Log",
    description: "Every upload is logged here. Watch statuses move from In Review → Processed → Accepted as we work through your queue.",
    tip: "top",
  },
];

// Role-specific steps, each gated by a flag below.
const REVIEW: Step = {
  page: "/admin/review",
  targetId: "tour-review-queue",
  title: "Review Queue",
  description: "Borderline submissions land here for a human decision. Approve, reject, or re-run the analysis — the live count in the sidebar shows what's pending.",
  tip: "bottom",
};
const ANALYTICS: Step = {
  page: "/admin/analytics",
  targetId: "tour-analytics",
  title: "Analytics",
  description: "See submission volume, acceptance rates, and points across your team — your window into how the program is performing.",
  tip: "bottom",
};
const INVOICES: Step = {
  page: "/admin/invoices",
  targetId: "tour-invoices",
  title: "Invoices",
  description: "Generate and track invoices for outstanding points. Org admins bill here; the superuser reviews and settles them.",
  tip: "bottom",
};
const STAFF: Step = {
  page: "/admin/staff",
  targetId: "tour-staff",
  title: "Your Staff",
  description: "Manage the uploaders in your organization — see who's active and how each member is contributing.",
  tip: "bottom",
};
const REFERRALS: Step = {
  page: "/referrals",
  targetId: "tour-referrals",
  title: "Referrals",
  description: "Share your referral link to invite uploaders into your organization, and watch your downline grow here.",
  tip: "bottom",
};
const ORGS: Step = {
  page: "/admin/orgs",
  targetId: "tour-orgs",
  title: "Organizations",
  description: "Create organizations and invite their admins. Each org gets its own admin, staff, and isolated analytics.",
  tip: "bottom",
};
const USERS: Step = {
  page: "/admin/users",
  targetId: "tour-users",
  title: "All Users",
  description: "Every user across all organizations, with their role, org, and status — manage access from one place.",
  tip: "bottom",
};
const TURK_ADMINS: Step = {
  page: "/admin/turk-admins",
  targetId: "tour-turk-admins",
  title: "Turk Admins",
  description: "Invite platform-level admins who can review submissions across every organization.",
  tip: "bottom",
};

export function TourOverlay() {
  const { user, error, isSuperuser, isTurkAdmin, isOrgAdmin, canReview, isAdmin } = useAuth();
  const [location, navigate] = useLocation();
  const [step, setStep] = useState<number | null>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight });
  const attempts = useRef(0);

  // Build the step list for this user's role. Order: the common uploader flow first,
  // then the admin surfaces this role can actually reach (so the tour never points at a
  // page the user isn't allowed to open).
  const steps = useMemo<Step[]>(() => {
    const s = [...COMMON];
    if (canReview) s.push(REVIEW);
    if (isAdmin) s.push(ANALYTICS);
    if (isOrgAdmin || isSuperuser) s.push(INVOICES);
    if (isOrgAdmin) s.push(STAFF, REFERRALS);
    if (isSuperuser) s.push(ORGS, USERS, TURK_ADMINS);
    return s;
  }, [isSuperuser, isTurkAdmin, isOrgAdmin, canReview, isAdmin]);

  // Init / resume once the user is provisioned. Navigates to the (resumed) step's page so the
  // tour is always visible — even if the user reloaded on a different page mid-tour.
  useEffect(() => {
    if (!user || error || steps.length === 0) return;
    if (localStorage.getItem(doneKey(user.id))) return;
    if (step !== null) return; // already initialized this session
    const stored = sessionStorage.getItem(stepKey(user.id));
    let s = stored !== null ? parseInt(stored, 10) : 0;
    if (isNaN(s) || s < 0 || s >= steps.length) s = 0;
    sessionStorage.setItem(stepKey(user.id), String(s));
    setStep(s);
    if (steps[s].page !== location) navigate(steps[s].page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, error, steps]);

  // Find and measure the target element, retrying after navigation/render.
  const findTarget = useCallback(() => {
    if (step === null) return;
    const el = document.getElementById(steps[step]?.targetId ?? "");
    if (el) {
      setRect(el.getBoundingClientRect());
      attempts.current = 0;
    } else if (attempts.current < 30) {
      attempts.current++;
      setTimeout(findTarget, 80);
    }
  }, [step, steps]);

  useEffect(() => {
    setRect(null);
    attempts.current = 0;
    const t = setTimeout(findTarget, 120);
    return () => clearTimeout(t);
  }, [findTarget, location]);

  useEffect(() => {
    const refresh = () => {
      setVp({ w: window.innerWidth, h: window.innerHeight });
      findTarget();
    };
    window.addEventListener("resize", refresh);
    window.addEventListener("scroll", refresh, true);
    return () => {
      window.removeEventListener("resize", refresh);
      window.removeEventListener("scroll", refresh, true);
    };
  }, [findTarget]);

  const markDone = useCallback(() => {
    if (user) {
      localStorage.setItem(doneKey(user.id), "1");
      sessionStorage.removeItem(stepKey(user.id));
    }
    setStep(null);
  }, [user]);

  // Skip / close: end the tour where they are.
  const dismiss = markDone;

  // Finish (completed all steps): end the tour and return to the Instructions page.
  const finish = useCallback(() => {
    markDone();
    navigate("/instructions");
  }, [markDone, navigate]);

  const go = useCallback((next: number) => {
    if (next >= steps.length) { finish(); return; }
    if (user) sessionStorage.setItem(stepKey(user.id), String(next));
    setStep(next);
    const nextPage = steps[next].page;
    if (nextPage !== location) navigate(nextPage);
  }, [location, navigate, finish, steps, user]);

  if (!user || error) return null;
  if (step === null || localStorage.getItem(doneKey(user.id))) return null;
  const cur = steps[step];
  if (!cur || location !== cur.page) return null;

  // Tooltip placement.
  const PAD = 10;
  const TW = Math.min(300, vp.w - 32);
  const TH = 190;

  let tx = (vp.w - TW) / 2;
  let ty = (vp.h - TH) / 2;
  let arrowSide: "top" | "bottom" | "none" = "none";

  if (rect) {
    const cx = rect.left + rect.width / 2;
    if (cur.tip === "bottom") {
      ty = rect.bottom + PAD + 16;
      tx = cx - TW / 2;
      arrowSide = "top";
    } else {
      ty = rect.top - PAD - TH - 16;
      tx = cx - TW / 2;
      arrowSide = "bottom";
    }
    tx = Math.max(16, Math.min(vp.w - TW - 16, tx));
    ty = Math.max(16, Math.min(vp.h - TH - 80, ty));
  }

  return (
    <>
      {/* Dimmed backdrop with spotlight cutout */}
      <svg
        className="pointer-events-none"
        style={{ position: "fixed", inset: 0, zIndex: 60, width: vp.w, height: vp.h }}
      >
        <defs>
          <mask id="turk-spotlight-mask">
            <rect width={vp.w} height={vp.h} fill="white" />
            {rect && (
              <rect
                x={rect.left - PAD}
                y={rect.top - PAD}
                width={rect.width + PAD * 2}
                height={rect.height + PAD * 2}
                rx={10}
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect
          width={vp.w}
          height={vp.h}
          fill="rgba(0,0,0,0.72)"
          mask="url(#turk-spotlight-mask)"
        />
        {rect && (
          <rect
            x={rect.left - PAD}
            y={rect.top - PAD}
            width={rect.width + PAD * 2}
            height={rect.height + PAD * 2}
            rx={10}
            fill="none"
            stroke="hsl(190 90% 50%)"
            strokeWidth="1.5"
            strokeOpacity="0.7"
          />
        )}
      </svg>

      {/* Tooltip card */}
      <div
        style={{ position: "fixed", left: tx, top: ty, width: TW, zIndex: 70 }}
        className="bg-card border border-primary/30 rounded-xl shadow-[0_8px_60px_rgba(0,0,0,0.9),0_0_0_1px_rgba(0,255,255,0.05)] p-5"
      >
        {arrowSide === "top" && rect && (
          <div
            style={{ position: "absolute", left: Math.max(20, Math.min(TW - 40, rect.left + rect.width / 2 - tx - 8)), top: -8 }}
            className="w-4 h-2 overflow-hidden"
          >
            <div className="w-4 h-4 bg-card border-l border-t border-primary/30 rotate-45 -translate-y-2.5 mx-auto" />
          </div>
        )}
        {arrowSide === "bottom" && rect && (
          <div
            style={{ position: "absolute", left: Math.max(20, Math.min(TW - 40, rect.left + rect.width / 2 - tx - 8)), bottom: -8 }}
            className="w-4 h-2 overflow-hidden"
          >
            <div className="w-4 h-4 bg-card border-r border-b border-primary/30 rotate-45 translate-y-0 mx-auto" />
          </div>
        )}

        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono font-bold text-muted-foreground">
              {step + 1} OF {steps.length}
            </span>
            <div className="flex gap-1">
              {steps.map((_, i) => (
                <div
                  key={i}
                  className={`rounded-full transition-all duration-300 ${
                    i === step ? "w-4 h-1.5 bg-primary" : i < step ? "w-1.5 h-1.5 bg-primary/40" : "w-1.5 h-1.5 bg-muted"
                  }`}
                />
              ))}
            </div>
          </div>
          <button
            onClick={dismiss}
            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            aria-label="Close tour"
          >
            <X size={14} />
          </button>
        </div>

        <h3 className="font-black text-sm uppercase tracking-widest text-primary mb-1">
          {cur.title}
        </h3>
        <p className="text-sm text-muted-foreground leading-relaxed mb-4">
          {cur.description}
        </p>

        <div className="flex items-center gap-2">
          {step > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="border-border h-8 px-3 gap-1 text-xs"
              onClick={() => go(step - 1)}
            >
              <ArrowLeft size={12} />
              Back
            </Button>
          )}
          <Button
            size="sm"
            className="flex-1 h-8 bg-primary text-primary-foreground font-bold uppercase tracking-wider hover:bg-primary/90 gap-1 text-xs shadow-[0_0_15px_rgba(0,255,255,0.25)]"
            onClick={() => go(step + 1)}
          >
            {step === steps.length - 1 ? "Finish Tour" : "Next"}
            {step < steps.length - 1 && <ArrowRight size={12} />}
          </Button>
          {step < steps.length - 1 && (
            <button
              onClick={dismiss}
              className="text-[10px] text-muted-foreground hover:text-foreground transition-colors whitespace-nowrap px-1"
            >
              Skip
            </button>
          )}
        </div>
      </div>
    </>
  );
}
