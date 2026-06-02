import { Switch, Route, Router as WouterRouter, Redirect, useLocation } from "wouter";
import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ClerkProvider } from "@clerk/react";
import { shadcn } from "@clerk/themes";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ReactNode } from "react";

import { AuthProvider, useAuth } from "@/lib/auth";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import Upload from "@/pages/Upload";
import Submissions from "@/pages/Submissions";
import Instructions from "@/pages/Instructions";
import Referrals from "@/pages/Referrals";
import ReviewQueue from "@/pages/admin/ReviewQueue";
import Organizations from "@/pages/admin/Organizations";
import Users from "@/pages/admin/Users";
import Staff from "@/pages/admin/Staff";
import TurkAdmins from "@/pages/admin/TurkAdmins";
import Analytics from "@/pages/admin/Analytics";
import Invoices from "@/pages/admin/Invoices";
import NotFound from "@/pages/not-found";
import { TourOverlay } from "@/components/TourOverlay";

const queryClient = new QueryClient();
const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");
const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string;
if (!clerkPubKey) throw new Error("Missing VITE_CLERK_PUBLISHABLE_KEY in artifacts/turk/.env");

// Capture an org referral/registration code as EARLY as possible — at module load,
// before Clerk can route a user with an existing Google account to sign-IN (where the
// /register ref-capture effect never runs). Persisted so the post-auth clerk_sync can
// attribute the account no matter which auth screen Clerk shows; cleared on successful
// sync (see lib/auth.tsx). This is the fix for "you can only sign in with an organization"
// hitting users who already had a Google/Clerk account.
try {
  const refFromUrl = new URLSearchParams(window.location.search).get("ref");
  if (refFromUrl) localStorage.setItem("turk_ref", refFromUrl);
} catch {
  /* localStorage unavailable — ignore */
}

// Clerk sign-in/up theming — matches the Turk dashboard (dark + cyan), per the Replit design.
const clerkAppearance = {
  theme: shadcn,
  cssLayerName: "clerk",
  options: {
    logoPlacement: "inside" as const,
    logoLinkUrl: basePath || "/",
    logoImageUrl: `${window.location.origin}${basePath}/logo.svg`,
  },
  variables: {
    colorPrimary: "hsl(190 90% 50%)",
    colorForeground: "hsl(0 0% 98%)",
    colorMutedForeground: "hsl(240 10% 70%)",
    colorDanger: "hsl(350 80% 60%)",
    colorBackground: "hsl(240 35% 9%)",
    colorInput: "hsl(240 30% 16%)",
    colorInputForeground: "hsl(0 0% 98%)",
    colorNeutral: "hsl(240 30% 16%)",
    fontFamily: "'Outfit', sans-serif",
    borderRadius: "0.5rem",
  },
  elements: {
    rootBox: "w-full flex justify-center",
    cardBox: "bg-[#15151e] border border-[#1c1c29] rounded-xl w-[440px] max-w-full overflow-hidden shadow-[0_0_30px_rgba(0,0,0,0.5)]",
    card: "!shadow-none !border-0 !bg-transparent !rounded-none",
    footer: "!shadow-none !border-0 !bg-transparent !rounded-none",
    headerTitle: "text-2xl font-black uppercase tracking-tight text-white",
    headerSubtitle: "text-muted-foreground font-medium",
    socialButtonsBlockButtonText: "!text-foreground font-semibold",
    formFieldLabel: "text-foreground font-semibold uppercase tracking-wider text-xs",
    footerActionLink: "text-primary hover:text-primary/80 font-bold",
    footerActionText: "text-muted-foreground",
    dividerText: "text-muted-foreground uppercase text-xs font-bold",
    identityPreviewEditButton: "text-primary",
    formFieldSuccessText: "text-green-500",
    alertText: "text-destructive",
    logoBox: "flex justify-center mb-4",
    logoImage: "h-12",
    socialButtonsBlockButton: "!bg-input !border !border-border !text-foreground hover:!bg-muted/60 transition-colors rounded-md",
    formButtonPrimary: "bg-primary text-[#06060f] font-bold uppercase tracking-wider hover:bg-primary/90 transition-colors shadow-[0_0_15px_rgba(0,255,255,0.3)]",
    formFieldInput: "bg-input border-border text-foreground rounded-md focus:ring-1 focus:ring-primary font-mono",
    footerAction: "bg-muted/30 border-t border-border mt-4 py-4 rounded-b-xl",
    dividerLine: "bg-border",
    alert: "bg-destructive/10 border-destructive/20 text-destructive",
    otpCodeFieldInput: "bg-input border-border text-foreground rounded-md",
    formFieldRow: "mb-4",
    main: "p-8",
  },
};

type Role = "superuser" | "turk_admin" | "admin" | "user";

function Loading() {
  return <div className="min-h-screen flex items-center justify-center text-muted-foreground">Loading…</div>;
}

function Denied() {
  const { error, logout } = useAuth();
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="max-w-md text-center bg-card border border-border rounded-xl p-8">
        <h1 className="text-xl font-bold mb-2">No access</h1>
        <p className="text-sm text-muted-foreground mb-6">
          {error || "Your account isn't linked to an organization. You need a valid invite or referral link."}
        </p>
        <button onClick={logout} className="text-sm font-bold uppercase tracking-wider text-primary">Sign out</button>
      </div>
    </div>
  );
}

function Protected({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { isSignedIn, user, loading, error } = useAuth();
  if (!isSignedIn && loading) return <Loading />;
  if (!isSignedIn) return <Redirect to="/login" />;
  if (error) return <Denied />; // signed in but couldn't be provisioned (no org/invite)
  if (!user) return <Loading />; // signed in, provisioning local account
  if (roles && !roles.includes(user.role as Role)) return <Redirect to="/dashboard" />;
  return <>{children}</>;
}

function RootRoute() {
  const { isSignedIn, loading } = useAuth();
  if (loading) return <Loading />;
  if (isSignedIn) return <Redirect to="/dashboard" />;
  return <Landing />;
}

function Router() {
  return (
    <Switch>
      <Route path="/login" component={Login} />
      <Route path="/register" component={Register} />

      <Route path="/" component={RootRoute} />
      <Route path="/dashboard"><Protected><Dashboard /></Protected></Route>
      <Route path="/upload"><Protected><Upload /></Protected></Route>
      <Route path="/submissions"><Protected><Submissions /></Protected></Route>
      <Route path="/referrals"><Protected roles={["admin"]}><Referrals /></Protected></Route>
      <Route path="/instructions"><Protected><Instructions /></Protected></Route>

      <Route path="/admin/review"><Protected roles={["superuser", "turk_admin"]}><ReviewQueue /></Protected></Route>
      <Route path="/admin/analytics"><Protected roles={["superuser", "turk_admin", "admin"]}><Analytics /></Protected></Route>
      <Route path="/admin/orgs"><Protected roles={["superuser"]}><Organizations /></Protected></Route>
      <Route path="/admin/turk-admins"><Protected roles={["superuser"]}><TurkAdmins /></Protected></Route>
      <Route path="/admin/users"><Protected roles={["superuser"]}><Users /></Protected></Route>
      <Route path="/admin/staff"><Protected roles={["admin"]}><Staff /></Protected></Route>
      <Route path="/admin/invoices"><Protected roles={["superuser", "admin"]}><Invoices /></Protected></Route>

      <Route component={NotFound} />
    </Switch>
  );
}

// New users land on the Instructions page on their first login. loginCount is incremented
// by the backend on each new Clerk session, so loginCount <= 1 means "first sign-in". The flag
// is keyed PER USER (not per browser) so that signing into a different account on the same
// machine still gets the first-run experience. We only redirect from the default landing spots
// ("/" or "/dashboard"), so returning users and normal navigation are never hijacked.
const firstRunKey = (id: string | number) => `turk_instructions_landed:${id}`;

function FirstRunRedirect() {
  const { user, error, loading } = useAuth();
  const [location, navigate] = useLocation();
  useEffect(() => {
    if (loading || error || !user) return;
    const key = firstRunKey(user.id);
    if (localStorage.getItem(key)) return;
    if ((user.loginCount ?? 0) > 1) {
      localStorage.setItem(key, "1"); // returning user — don't bounce, just remember
      return;
    }
    if (location === "/" || location === "/dashboard") {
      localStorage.setItem(key, "1");
      navigate("/instructions");
    }
  }, [user, error, loading, location, navigate]);
  return null;
}


function App() {
  return (
    <ClerkProvider
      publishableKey={clerkPubKey}
      appearance={clerkAppearance}
      signInForceRedirectUrl="/dashboard"
      signUpForceRedirectUrl="/dashboard"
    >
      <WouterRouter base={basePath}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <TooltipProvider>
              <Router />
              <FirstRunRedirect />
              <TourOverlay />
              <Toaster />
            </TooltipProvider>
          </AuthProvider>
        </QueryClientProvider>
      </WouterRouter>
    </ClerkProvider>
  );
}

export default App;
