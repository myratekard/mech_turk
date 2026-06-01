import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useLocation } from "wouter";
import { useAuth as useClerkAuth, useUser, useClerk, useOrganizationList } from "@clerk/react";
import { setAuthTokenGetter } from "@workspace/api-client-react";
import { api, setTokenGetter, User } from "@/lib/api";

interface AuthState {
  user: User | null;       // authoritative local user (effective role/org from /me)
  loading: boolean;
  isSignedIn: boolean;
  error: string | null;    // set when a signed-in user couldn't be provisioned (no org/invite)
  logout: () => void;
  isSuperuser: boolean;
  isTurkAdmin: boolean;
  isOrgAdmin: boolean;
  canReview: boolean;      // superuser or turk_admin
  isAdmin: boolean;        // any admin-ish (superuser/turk_admin/org admin) — for nav grouping
}

const FALLBACK: AuthState = {
  user: null, loading: true, isSignedIn: false, error: null, logout: () => {},
  isSuperuser: false, isTurkAdmin: false, isOrgAdmin: false, canReview: false, isAdmin: false,
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken, orgId } = useClerkAuth();
  const { user: clerkUser } = useUser();
  const { signOut } = useClerk();
  const { isLoaded: orgsLoaded, userMemberships, setActive } = useOrganizationList({
    userMemberships: true,
  });

  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [, setLocation] = useLocation();

  // Route API bearer tokens through Clerk's session token.
  useEffect(() => {
    const getter = async () => {
      try {
        return (await getToken()) ?? null;
      } catch {
        return null;
      }
    };
    setTokenGetter(getter);
    setAuthTokenGetter(getter);
  }, [getToken]);

  const memberships = userMemberships?.data ?? [];

  // One org per user: if signed in with a membership but no active org, activate it
  // so the session token carries org_id/org_role (→ correct admin/member role).
  useEffect(() => {
    if (!isLoaded || !isSignedIn || orgId || !orgsLoaded) return;
    const first = memberships[0];
    if (first && setActive) setActive({ organization: first.organization.id });
  }, [isLoaded, isSignedIn, orgId, orgsLoaded, memberships.length, setActive]);

  // Provision the local user, then read the authoritative role/org from /me.
  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      setUser(null);
      setLoading(false);
      return;
    }
    // Hold until the active org is resolved when the user has a membership.
    if (!orgId && orgsLoaded && memberships.length > 0) return;

    const email = clerkUser?.primaryEmailAddress?.emailAddress;
    const ref = localStorage.getItem("turk_ref") || undefined;
    setLoading(true);
    setError(null);
    api
      .clerkSync(email, ref) // provision local mirror (strictly org-tied)
      .then((synced) => {
        // First 3 logins (fresh Clerk session): land on Instructions, then Dashboard after.
        if (synced?.justLoggedIn && (synced.loginCount ?? 99) <= 3) {
          setLocation("/instructions");
        }
        return api.me(); // authoritative effective role/org from token claims
      })
      .then((u) => {
        setUser(u);
        localStorage.removeItem("turk_ref");
      })
      .catch((e) => {
        setUser(null);
        setError(e?.message || "Your account is not linked to an organization.");
      })
      .finally(() => setLoading(false));
  }, [isLoaded, isSignedIn, orgId, orgsLoaded, memberships.length, clerkUser?.id]);

  const logout = () => signOut();

  return (
    <AuthContext.Provider
      value={{
        user,
        loading: !isLoaded || loading,
        isSignedIn: !!isSignedIn,
        error,
        logout,
        isSuperuser: user?.role === "superuser",
        isTurkAdmin: user?.role === "turk_admin",
        isOrgAdmin: user?.role === "admin",
        canReview: user?.role === "superuser" || user?.role === "turk_admin",
        isAdmin: ["superuser", "turk_admin", "admin"].includes(user?.role || ""),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  return useContext(AuthContext) ?? FALLBACK;
}
