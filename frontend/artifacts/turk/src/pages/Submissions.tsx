import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Shell } from "@/components/layout/Shell";
import { useListSubmissions, getListSubmissionsQueryKey } from "@workspace/api-client-react";
import { api } from "@/lib/api";
import { format } from "date-fns";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ChevronLeft, ChevronRight, Activity, ExternalLink, Filter, Flag } from "lucide-react";
import type { ListSubmissionsStatus } from "@workspace/api-client-react";

const DISPUTABLE = ["accepted", "invalid"];

export default function Submissions() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<ListSubmissionsStatus | "all">("all");
  const [disputingId, setDisputingId] = useState<number | null>(null);
  const [disputeError, setDisputeError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const limit = 10;

  const params = {
    page,
    limit,
    ...(statusFilter !== "all" ? { status: statusFilter } : {}),
  };

  async function handleDispute(id: number) {
    if (!confirm("Dispute this decision? It will be sent back for human review. You can only dispute a submission once.")) return;
    setDisputingId(id);
    setDisputeError(null);
    try {
      await api.disputeSubmission(id);
      // Reflect the new state immediately so the row flips to DISPUTED / the button is gone.
      queryClient.setQueryData(getListSubmissionsQueryKey(params), (old: any) =>
        old
          ? {
              ...old,
              submissions: old.submissions.map((s: any) =>
                s.id === id ? { ...s, status: "in_review", disputed: true } : s,
              ),
            }
          : old,
      );
      await queryClient.invalidateQueries(); // sync list + dashboard counts with the server
    } catch (e: any) {
      setDisputeError(e?.message || "Failed to dispute submission.");
    } finally {
      setDisputingId(null);
    }
  }

  const { data, isLoading } = useListSubmissions(params, {
    query: {
      queryKey: getListSubmissionsQueryKey(params),
      refetchInterval: 10000,
    }
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case "accepted": return "bg-green-500/10 text-green-500 border-green-500/20";
      case "in_review": return "bg-amber-500/10 text-amber-500 border-amber-500/20";
      case "invalid": return "bg-red-500/10 text-red-500 border-red-500/20";
      case "duplicate": return "bg-fuchsia-500/10 text-fuchsia-500 border-fuchsia-500/20";
      case "unsupported": return "bg-slate-500/10 text-slate-500 border-slate-500/20";
      case "processed": return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case "disputed": return "bg-violet-500/10 text-violet-500 border-violet-500/20";
      default: return "bg-muted text-muted-foreground";
    }
  };

  const getStatusLabel = (status: string) => {
    return status.replace("_", " ").toUpperCase();
  };

  // A disputed row is shown as DISPUTED (it sits in the review queue) until a reviewer decides.
  const displayStatus = (sub: any) => (sub.disputed ? "disputed" : sub.status);

  const totalPages = data ? Math.ceil(data.total / limit) : 1;

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full flex flex-col h-full">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-black uppercase tracking-tight">Intel Log</h1>
            <p className="text-muted-foreground font-medium">History of your operations and earnings.</p>
          </div>
          
          <div className="flex items-center gap-3 bg-card border border-border rounded-lg p-1">
            <div className="px-3 flex items-center gap-2 text-muted-foreground">
              <Filter size={14} />
              <span className="text-xs font-bold uppercase tracking-wider">Filter:</span>
            </div>
            <Select 
              value={statusFilter} 
              onValueChange={(v) => { setStatusFilter(v as any); setPage(1); }}
            >
              <SelectTrigger className="w-[140px] h-8 text-xs border-0 bg-transparent focus:ring-0 shadow-none font-mono">
                <SelectValue placeholder="All Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">ALL STATUS</SelectItem>
                <SelectItem value="in_review">IN REVIEW</SelectItem>
                <SelectItem value="accepted">ACCEPTED</SelectItem>
                <SelectItem value="invalid">INVALID</SelectItem>
                <SelectItem value="duplicate">DUPLICATE</SelectItem>
                <SelectItem value="unsupported">UNSUPPORTED</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {disputeError && (
          <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2 text-sm text-red-500">
            {disputeError}
          </div>
        )}

        <div className="bg-card border border-border rounded-xl shadow-sm flex-1 flex flex-col overflow-hidden">
          <div className="overflow-x-auto flex-1">
            <Table>
              <TableHeader className="bg-muted/30 sticky top-0 z-10">
                <TableRow className="hover:bg-transparent border-border">
                  <TableHead className="w-[80px] font-bold uppercase text-xs tracking-wider">Image</TableHead>
                  <TableHead className="font-bold uppercase text-xs tracking-wider">Details</TableHead>
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
                    </TableRow>
                  ))
                ) : data && data.submissions.length > 0 ? (
                  data.submissions.map((sub) => (
                    <TableRow key={sub.id} className="border-border hover:bg-muted/20 transition-colors group">
                      <TableCell>
                        <div className="w-12 h-12 rounded overflow-hidden bg-muted border border-border relative">
                          <img src={sub.imageUrl} alt={sub.fileName || "Screenshot"} className="w-full h-full object-cover" />
                          <a 
                            href={sub.imageUrl} 
                            target="_blank" 
                            rel="noreferrer"
                            className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity"
                          >
                            <ExternalLink size={14} className="text-white" />
                          </a>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="font-semibold text-sm truncate max-w-[200px] md:max-w-[300px]">
                          {sub.fileName || `Submission #${sub.id}`}
                        </div>
                        {sub.platform && (
                          <div className="text-xs text-muted-foreground mt-1 font-mono uppercase">
                            Platform: <span className="text-foreground">{sub.platform}</span>
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={getStatusColor(displayStatus(sub))}>
                          {getStatusLabel(displayStatus(sub))}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="font-black font-mono text-primary tracking-tight">
                          {sub.points > 0 ? `+${sub.points}` : "-"}
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground font-mono text-xs">
                        {format(new Date(sub.createdAt), "MMM d, yyyy")}
                        <div className="opacity-50 mt-1">{format(new Date(sub.createdAt), "HH:mm")}</div>
                      </TableCell>
                      <TableCell className="text-right">
                        {(sub as any).disputed ? (
                          <span className="text-xs text-muted-foreground">Awaiting review</span>
                        ) : DISPUTABLE.includes(sub.status) ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 gap-1 text-xs border-border"
                            disabled={disputingId === sub.id}
                            onClick={() => handleDispute(sub.id)}
                          >
                            <Flag size={12} />
                            {disputingId === sub.id ? "..." : "Dispute"}
                          </Button>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={6} className="h-[400px] text-center">
                      <div className="flex flex-col items-center justify-center text-muted-foreground">
                        <Activity size={48} className="mb-4 opacity-20" />
                        <h3 className="text-lg font-bold mb-1 text-foreground">No Records Found</h3>
                        <p className="text-sm">We couldn't find any submissions matching these criteria.</p>
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
                <Button 
                  variant="outline" 
                  size="icon"
                  className="h-8 w-8 border-border"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1 || isLoading}
                >
                  <ChevronLeft size={16} />
                </Button>
                <div className="text-xs font-bold font-mono px-2">
                  {page} / {totalPages || 1}
                </div>
                <Button 
                  variant="outline" 
                  size="icon"
                  className="h-8 w-8 border-border"
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages || isLoading}
                >
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
