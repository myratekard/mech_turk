// Thin fetch wrapper for mech_turk's auth/admin/referral endpoints.
// Bearer token is read from localStorage; the generated client uses the same token
// via setAuthTokenGetter (wired in auth.tsx).

// Bearer token comes from Clerk (set by AuthProvider via setTokenGetter).
type TokenGetter = () => Promise<string | null> | string | null;
let _tokenGetter: TokenGetter = () => null;
export function setTokenGetter(fn: TokenGetter) {
  _tokenGetter = fn;
}

async function apiFetch<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) headers.set("Content-Type", "application/json");
  const token = await _tokenGetter();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      detail = data.detail || data.error || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ---- types (mirror the backend wire models) ----
export interface User {
  id: number;
  username: string;
  email?: string | null;
  role: "superuser" | "admin" | "user";
  orgId?: number | null;
  referredBy?: number | null;
  referralCode: string;
  blocked?: boolean;
  createdAt: string;
}

export interface Analytics {
  scope: "org" | "platform";
  orgName?: string | null;
  users: number;
  blockedUsers: number;
  totalSubmissions: number;
  accepted: number;
  invalid: number;
  inReview: number;
  duplicate?: number;
  unsupported?: number;
  totalPoints: number;
}

export interface UserStat {
  userId: number;
  userKey: string;
  username: string;
  total: number;
  accepted: number;
  invalid: number;
  inReview: number;
  duplicate: number;
  unsupported: number;
  points: number;
}
export interface Org {
  id: string;            // Clerk organization id
  name: string;
  createdAt?: string | null;
  emailSent?: boolean | null;
}
export interface RefInfo {
  valid: boolean;
  role?: string;
  orgName?: string;
  inviter?: string;
}
export interface Invoice {
  id: number;
  orgId: string;
  orgName?: string | null;
  status: "pending" | "settled";
  submissionCount: number;
  totalPoints: number;
  rate: number;
  amount: number;
  currency: string;
  createdBy?: string | null;
  createdAt: string;
  settledBy?: string | null;
  settledAt?: string | null;
}
export interface InvoiceLineItem {
  id: number;
  userId: string;
  username?: string | null;
  platform?: string | null;
  handle?: string | null;
  status: string;
  points: number;
  createdAt: string;
}
export interface InvoiceDetail extends Invoice {
  items: InvoiceLineItem[];
}
export interface OutstandingSummary {
  orgId: string;
  count: number;
  points: number;
  rate: number;
  amount: number;
  currency: string;
}
export interface ReviewItem {
  id: number;
  userId: string;
  imageUrl: string;
  platform?: string;
  fileName?: string;
  status: string;
  createdAt: string;
  verified?: boolean;
  confidence?: number;
  needsReview?: boolean;
  profile?: any;
  reasoning?: string;
  africanDescent?: boolean | null;
}

// ---- auth (Clerk-backed; login/signup happen in Clerk UI) ----
export const api = {
  me: () => apiFetch<User>("/api/auth/me"),
  refInfo: (code: string) => apiFetch<RefInfo>(`/api/auth/ref/${code}`),
  clerkSync: (email?: string, ref?: string) =>
    apiFetch<User>("/api/auth/clerk/sync", { method: "POST", body: JSON.stringify({ email, ref }) }),

  // admin
  reviewQueue: (page = 1, limit = 20) =>
    apiFetch<{ items: ReviewItem[]; total: number; page: number; limit: number }>(
      `/api/admin/review-queue?page=${page}&limit=${limit}`,
    ),
  approve: (id: number) => apiFetch(`/api/admin/submissions/${id}/approve`, { method: "POST" }),
  reject: (id: number) => apiFetch(`/api/admin/submissions/${id}/reject`, { method: "POST" }),
  rerun: (id: number) => apiFetch(`/api/admin/submissions/${id}/rerun`, { method: "POST" }),
  listOrgs: () => apiFetch<Org[]>("/api/admin/orgs"),
  createOrg: (name: string, adminEmail?: string) =>
    apiFetch<Org>("/api/admin/orgs", { method: "POST", body: JSON.stringify({ name, adminEmail }) }),
  listUsers: () => apiFetch<User[]>("/api/admin/users"),
  inviteStaff: (email: string) =>
    apiFetch<{ ok: boolean; emailSent: boolean }>("/api/admin/staff/invite", {
      method: "POST", body: JSON.stringify({ email }),
    }),
  listStaff: () => apiFetch<{ email: string; name: string; role: string }[]>("/api/admin/staff"),
  inviteTurkAdmin: (email: string) =>
    apiFetch<{ ok: boolean; emailSent: boolean }>("/api/admin/turk-admins/invite", {
      method: "POST", body: JSON.stringify({ email }),
    }),
  listTurkAdmins: () => apiFetch<User[]>("/api/admin/turk-admins"),
  blockUser: (id: number) => apiFetch<User>(`/api/admin/users/${id}/block`, { method: "POST" }),
  unblockUser: (id: number) => apiFetch<User>(`/api/admin/users/${id}/unblock`, { method: "POST" }),
  analytics: () => apiFetch<Analytics>("/api/admin/analytics"),
  userAnalytics: () => apiFetch<UserStat[]>("/api/admin/analytics/users"),

  // referrals (any user)
  myReferrals: () => apiFetch<User[]>("/api/me/referrals"),

  // submissions (owner) — contest a decided submission back into review (once only)
  disputeSubmission: (id: number) =>
    apiFetch(`/api/submissions/${id}/dispute`, { method: "POST" }),

  // invoices — org admin generates from outstanding points; superuser settles
  invoiceOutstanding: () => apiFetch<OutstandingSummary>("/api/admin/invoices/outstanding"),
  generateInvoice: () => apiFetch<Invoice>("/api/admin/invoices", { method: "POST" }),
  listInvoices: () => apiFetch<Invoice[]>("/api/admin/invoices"),
  getInvoice: (id: number) => apiFetch<InvoiceDetail>(`/api/admin/invoices/${id}`),
  settleInvoice: (id: number) => apiFetch<Invoice>(`/api/admin/invoices/${id}/settle`, { method: "POST" }),
};

// Build a registration link from any referral/registration code.
export function registrationLink(code: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${window.location.origin}${base}/register?ref=${code}`;
}
