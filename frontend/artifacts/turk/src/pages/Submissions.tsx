import { useState } from "react";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/layout/Shell";
import { useListSubmissions, getListSubmissionsQueryKey } from "@workspace/api-client-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { format } from "date-fns";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Link } from "wouter";
import { ChevronLeft, ChevronRight, Activity, ExternalLink, Filter, Flag, CheckCircle2, UploadCloud, AlertTriangle } from "lucide-react";
import type { ListSubmissionsStatus } from "@workspace/api-client-react";

const DISPUTABLE = ["accepted", "invalid"];

// Display for the African classification flag (admin view-all).
const AFRICAN: Record<string, { label: string; cls: string }> = {
  african: { label: "African", cls: "text-green-500 border-green-500/30" },
  non_african: { label: "Non-African", cls: "text-red-500 border-red-500/30" },
  generic: { label: "Generic", cls: "text-fuchsia-400 border-fuchsia-500/30" },
  unclear: { label: "Unclear", cls: "text-muted-foreground border-border" },
};

export default function Submissions() {
  const { canReview, user } = useAuth();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<ListSubmissionsStatus | "all">("all");
  const [scope, setScope] = useState<"mine" | "all">("all");        // reviewers only
  const [orgFilter, setOrgFilter] = useState<string>("all");
  const [africanFilter, setAfricanFilter] = useState<string>("all");
  const [userFilter, setUserFilter] = useState<string>("");
  const [disputingId, setDisputingId] = useState<number | null>(null);
  const [disputeError, setDisputeError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const limit = 10;

  const adminMode = !!canReview;       // superuser / turk_admin get the platform-wide browser
  const adminAll = adminMode && scope === "all";

  // Normal users: own submissions via the generated client (disabled for reviewers).
  const ownParams = { page, limit, ...(statusFilter !== "all" ? { status: statusFilter } : {}) };
  const { data: ownData, isLoading: ownLoading } = useListSubmissions(ownParams, {
    query: { queryKey: getListSubmissionsQueryKey(ownParams), refetchInterval: 10000, enabled: !adminMode },
  });

  // Reviewers: platform-wide (or own) via the admin endpoint, with org + African filters.
  const adminParams = {
    page, limit, mine: scope === "mine",
    ...(statusFilter !== "all" ? { status: statusFilter } : {}),
    ...(orgFilter !== "all" ? { org_id: orgFilter } : {}),
    ...(africanFilter !== "all" ? { african: africanFilter } : {}),
    ...(userFilter.trim() ? { user: userFilter.trim() } : {}),
  };
  const adminQ = useQuery({
    queryKey: ["adminSubs", adminParams],
    queryFn: () => api.adminSubmissions(adminParams),
    enabled: adminMode,
    refetchInterval: 10000,
  });
  const orgsQ = useQuery({ queryKey: ["adminSubOrgs"], queryFn: () => api.adminSubmissionOrgs(), enabled: adminMode });

  const data: any = adminMode ? adminQ.data : ownData;
  const isLoading = adminMode ? adminQ.isLoading : ownLoading;

  async function handleDispute(id: number) {
    if (!confirm("Dispute this decision? It will be sent back for human review. You can only dispute a submission once.")) return;
    setDisputingId(id);
    setDisputeError(null);
    try {
      await api.disputeSubmission(id);
      await queryClient.invalidateQueries();
    } catch (e: any) {
      setDisputeError(e?.message || "Failed to dispute submission.");
    } finally {
      setDisputingId(null);
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "accepted": return "bg-green-500/10 text-green-500 border-green-500/20";
      case "queued":
      case "processing": return "bg-primary/10 text-primary border-primary/20";
      case "in_review": return "bg-amber-500/10 text-amber-500 border-amber-500/20";
      case "invalid": return "bg-red-500/10 text-red-500 border-red-500/20";
      case "duplicate": return "bg-fuchsia-500/10 text-fuchsia-500 border-fuchsia-500/20";
      case "unsupported": return "bg-slate-500/10 text-slate-500 border-slate-500/20";
      case "processed": return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case "disputed": return "bg-violet-500/10 text-violet-500 border-violet-500/20";
      default: return "bg-muted text-muted-foreground";
    }
  };
  const getStatusLabel = (status: string) => status.replace("_", " ").toUpperCase();
  const displayStatus = (sub: any) => (sub.disputed && sub.status === "in_review" ? "disputed" : sub.status);
  const isOwn = (sub: any) => !adminMode || String(sub.userId) === String(user?.id);

  const totalPages = data ? Math.ceil(data.total / limit) : 1;
  const colSpan = 6;

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full flex flex-col h-full">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
          <div>
            <h1 className="text-3xl font-black uppercase tracking-tight">
              {adminAll ? "All Submissions" : "My Submissions"}
            </h1>
            <p className="text-muted-foreground font-medium">
              {adminAll ? "Every uploader's submissions across the platform." : "All your uploads and the points you've earned."}
            </p>
          </div>
          <Link href="/upload">
            <Button className="gap-2 font-bold uppercase tracking-wide bg-primary text-primary-foreground hover:bg-primary/90 shadow-[0_0_15px_rgba(0,255,255,0.3)]">
              <UploadCloud size={16} /> Upload
            </Button>
          </Link>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          {adminMode && (
            <div className="flex items-center bg-card border border-border rounded-lg p-1">
              {(["all", "mine"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => { setScope(s); setPage(1); }}
                  className={`text-xs font-bold uppercase tracking-wider px-3 py-1.5 rounded-md transition-colors ${
                    scope === s ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {s === "all" ? "All" : "Mine"}
                </button>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2 bg-card border border-border rounded-lg p-1">
            <span className="px-2 flex items-center gap-2 text-muted-foreground"><Filter size={14} /></span>
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v as any); setPage(1); }}>
              <SelectTrigger className="w-[130px] h-8 text-xs border-0 bg-transparent focus:ring-0 shadow-none font-mono"><SelectValue placeholder="All Status" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">ALL STATUS</SelectItem>
                <SelectItem value="processing">PROCESSING</SelectItem>
                <SelectItem value="in_review">IN REVIEW</SelectItem>
                <SelectItem value="accepted">ACCEPTED</SelectItem>
                <SelectItem value="invalid">INVALID</SelectItem>
                <SelectItem value="duplicate">DUPLICATE</SelectItem>
                <SelectItem value="unsupported">UNSUPPORTED</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {adminAll && (
            <>
              <Input
                value={userFilter}
                onChange={(e) => { setUserFilter(e.target.value); setPage(1); }}
                placeholder="Filter by user (name/email)…"
                className="h-10 w-[220px] text-xs"
              />
              <div className="flex items-center gap-2 bg-card border border-border rounded-lg p-1">
                <Select value={orgFilter} onValueChange={(v) => { setOrgFilter(v); setPage(1); }}>
                  <SelectTrigger className="w-[150px] h-8 text-xs border-0 bg-transparent focus:ring-0 shadow-none font-mono"><SelectValue placeholder="All Orgs" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">ALL ORGS</SelectItem>
                    {(orgsQ.data || []).map((o) => (
                      <SelectItem key={o.id} value={o.id}>{o.name || o.id}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2 bg-card border border-border rounded-lg p-1">
                <Select value={africanFilter} onValueChange={(v) => { setAfricanFilter(v); setPage(1); }}>
                  <SelectTrigger className="w-[150px] h-8 text-xs border-0 bg-transparent focus:ring-0 shadow-none font-mono"><SelectValue placeholder="African: All" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">AFRICAN: ALL</SelectItem>
                    <SelectItem value="african">AFRICAN</SelectItem>
                    <SelectItem value="non_african">NON-AFRICAN</SelectItem>
                    <SelectItem value="generic">GENERIC</SelectItem>
                    <SelectItem value="unclear">UNCLEAR</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </>
          )}
        </div>

        {disputeError && (
          <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2 text-sm text-red-500">{disputeError}</div>
        )}

        <div id="tour-submissions-list" className="bg-card border border-border rounded-xl shadow-sm flex-1 flex flex-col overflow-hidden">
          <div className="overflow-x-auto flex-1">
            <Table>
              <TableHeader className="bg-muted/30 sticky top-0 z-10">
                <TableRow className="hover:bg-transparent border-border">
                  <TableHead className="w-[80px] font-bold uppercase text-xs tracking-wider">Image</TableHead>
                  <TableHead className="font-bold uppercase text-xs tracking-wider">{adminAll ? "Details / Uploader" : "Details"}</TableHead>
                  <TableHead className="font-bold uppercase text-xs tracking-wider">Status</TableHead>
                  <TableHead className="font-bold uppercase text-xs tracking-wider">Points</TableHead>
                  <TableHead className="text-right font-bold uppercase text-xs tracking-wider">Date</TableHead>
                  <TableHead className="text-right font-bold uppercase text-xs tracking-wider">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  [...Array(5)].map((_, i) => (
                    <TableRow key={i} className="border-border">
                      <TableCell><Skeleton className="w-12 h-12 rounded bg-muted/50" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-32 bg-muted/50 mb-2" /><Skeleton className="h-3 w-16 bg-muted/50" /></TableCell>
                      <TableCell><Skeleton className="h-6 w-20 rounded-full bg-muted/50" /></TableCell>
                      <TableCell><Skeleton className="h-5 w-16 bg-muted/50" /></TableCell>
                      <TableCell className="text-right"><Skeleton className="h-4 w-24 bg-muted/50 ml-auto" /></TableCell>
                      <TableCell />
                    </TableRow>
                  ))
                ) : data && data.submissions.length > 0 ? (
                  data.submissions.map((sub: any) => (
                    <TableRow key={sub.id} className="border-border hover:bg-muted/20 transition-colors group">
                      <TableCell>
                        <div className="w-12 h-12 rounded overflow-hidden bg-muted border border-border relative">
                          <img src={sub.imageUrl} alt={sub.fileName || "Screenshot"} className="w-full h-full object-cover" />
                          <a href={sub.imageUrl} target="_blank" rel="noreferrer"
                            className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                            <ExternalLink size={14} className="text-white" />
                          </a>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="font-semibold text-sm truncate max-w-[200px] md:max-w-[300px]">
                          {sub.acctHandle ? `@${sub.acctHandle}` : sub.fileName || `Submission #${sub.id}`}
                        </div>
                        {sub.platform && (
                          <div className="text-xs text-muted-foreground mt-1 font-mono uppercase">
                            {sub.platform}
                          </div>
                        )}
                        {adminAll && (
                          <div className="text-xs text-muted-foreground mt-1 truncate max-w-[260px]">
                            by <span className="text-foreground font-semibold">{sub.username || `user ${sub.userId}`}</span>
                            {sub.orgName ? <span className="text-muted-foreground"> · {sub.orgName}</span> : null}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={getStatusColor(displayStatus(sub))}>
                          {getStatusLabel(displayStatus(sub))}
                        </Badge>
                        {adminMode && sub.africanClass && (
                          <div className="mt-1">
                            <Badge variant="outline" className={`text-[10px] ${AFRICAN[sub.africanClass]?.cls || "text-muted-foreground border-border"}`}>
                              {AFRICAN[sub.africanClass]?.label || sub.africanClass}
                            </Badge>
                          </div>
                        )}
                        {sub.dupKind === "self" && (
                          <div className="text-[10px] text-amber-500 mt-1 flex items-center gap-1" title="Re-uploaded the same image"><AlertTriangle size={11} /> Duplicate image</div>
                        )}
                        {sub.dupKind === "regular" && (
                          <div className="text-[10px] text-amber-500 mt-1 flex items-center gap-1" title="This account has already been captured"><AlertTriangle size={11} /> Exists</div>
                        )}
                        {sub.settled && (
                          <div className="text-[10px] text-green-500 mt-1 flex items-center gap-1" title="Paid out"><CheckCircle2 size={11} /> Settled{sub.settledVia ? ` via ${sub.settledVia}` : ""}</div>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className={`font-black font-mono tracking-tight ${sub.points > 0 ? "text-primary" : sub.points < 0 ? "text-red-500" : "text-muted-foreground"}`}>
                          {sub.points > 0 ? `+${sub.points}` : sub.points < 0 ? sub.points : "—"}
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground font-mono text-xs">
                        {format(new Date(sub.createdAt), "MMM d, yyyy")}
                        <div className="opacity-50 mt-1">{format(new Date(sub.createdAt), "HH:mm")}</div>
                      </TableCell>
                      <TableCell className="text-right">
                        {sub.disputed ? (
                          <span className="text-xs text-muted-foreground">{sub.status === "in_review" ? "Awaiting review" : "Disputed"}</span>
                        ) : isOwn(sub) && DISPUTABLE.includes(sub.status) ? (
                          <Button variant="outline" size="sm" className="h-7 gap-1 text-xs border-border"
                            disabled={disputingId === sub.id} onClick={() => handleDispute(sub.id)}>
                            <Flag size={12} />{disputingId === sub.id ? "..." : "Dispute"}
                          </Button>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={colSpan} className="h-[400px] text-center">
                      <div className="flex flex-col items-center justify-center text-muted-foreground">
                        <Activity size={48} className="mb-4 opacity-20" />
                        <h3 className="text-lg font-bold mb-1 text-foreground">Nothing here yet</h3>
                        <p className="text-sm">No submissions match this filter.</p>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          {data && data.total > 0 && (
            <div className="p-4 border-t border-border flex items-center justify-between bg-muted/10 mt-auto">
              <div className="text-xs font-mono text-muted-foreground">
                SHOWING <span className="font-bold text-foreground">{(page - 1) * limit + 1}</span> TO <span className="font-bold text-foreground">{Math.min(page * limit, data.total)}</span> OF <span className="font-bold text-foreground">{data.total}</span>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="icon" className="h-8 w-8 border-border" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1 || isLoading}>
                  <ChevronLeft size={16} />
                </Button>
                <div className="text-xs font-bold font-mono px-2">{page} / {totalPages || 1}</div>
                <Button variant="outline" size="icon" className="h-8 w-8 border-border" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages || isLoading}>
                  <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Shell>
  );
}
