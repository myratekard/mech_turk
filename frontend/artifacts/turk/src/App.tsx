import { Switch, Route, Router as WouterRouter, Redirect } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ClerkProvider } from "@clerk/react";
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
import NotFound from "@/pages/not-found";

const queryClient = new QueryClient();
const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");
const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string;
if (!clerkPubKey) throw new Error("Missing VITE_CLERK_PUBLISHABLE_KEY in artifacts/turk/.env");

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

      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <ClerkProvider
      publishableKey={clerkPubKey}
      signInForceRedirectUrl="/dashboard"
      signUpForceRedirectUrl="/dashboard"
    >
      <WouterRouter base={basePath}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <TooltipProvider>
              <Router />
              <Toaster />
            </TooltipProvider>
          </AuthProvider>
        </QueryClientProvider>
      </WouterRouter>
    </ClerkProvider>
  );
}

export default App;
