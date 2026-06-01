import { Shell } from "@/components/layout/Shell";
import { 
  useGetDashboardSummary, 
  getGetDashboardSummaryQueryKey,
  useGetRecentSubmissions,
  getGetRecentSubmissionsQueryKey
} from "@workspace/api-client-react";
import { Link } from "wouter";
import { format } from "date-fns";
import { Zap, CheckCircle2, Clock, Activity, BarChart3, XCircle, Copy, ImageOff, UploadCloud } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function Dashboard() {
  const { data: summary, isLoading: isSummaryLoading } = useGetDashboardSummary({
    query: { queryKey: getGetDashboardSummaryQueryKey(), refetchInterval: 10000 }
  });

  const { data: recent, isLoading: isRecentLoading } = useGetRecentSubmissions({
    query: { queryKey: getGetRecentSubmissionsQueryKey(), refetchInterval: 10000 }
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case "accepted": return "bg-green-500/10 text-green-500 border-green-500/20";
      case "in_review": return "bg-amber-500/10 text-amber-500 border-amber-500/20";
      case "invalid": return "bg-red-500/10 text-red-500 border-red-500/20";
      case "duplicate": return "bg-fuchsia-500/10 text-fuchsia-500 border-fuchsia-500/20";
      case "unsupported": return "bg-slate-500/10 text-slate-500 border-slate-500/20";
      case "processed": return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      default: return "bg-muted text-muted-foreground";
    }
  };

  const getStatusLabel = (status: string) => {
    return status.replace("_", " ").toUpperCase();
  };

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-black uppercase tracking-tight">Dashboard</h1>
            <p className="text-muted-foreground font-medium">Here's how you're doing.</p>
          </div>
          <div className="flex items-center gap-3 w-full sm:w-auto">
            {summary && (
              <div className="flex items-center gap-2 px-4 py-2 bg-card border border-border rounded-lg shadow-sm">
                <Activity size={16} className="text-primary" />
                <span className="text-sm font-bold text-muted-foreground">UPDATED TODAY:</span>
                <span className="text-sm font-black font-mono">{summary.updatedToday}</span>
              </div>
            )}
            <Link href="/upload" className="flex-1 sm:flex-none">
              <Button className="w-full gap-2 font-bold uppercase tracking-wide bg-primary text-primary-foreground hover:bg-primary/90 shadow-[0_0_15px_rgba(0,255,255,0.3)]">
                <UploadCloud size={16} />
                Upload
              </Button>
            </Link>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-10">
          <StatCard 
            title="Total Points" 
            value={summary?.totalPoints} 
            icon={Zap} 
            color="text-primary" 
            loading={isSummaryLoading} 
          />
          <StatCard 
            title="Accepted" 
            value={summary?.accepted} 
            icon={CheckCircle2} 
            color="text-green-500" 
            loading={isSummaryLoading} 
          />
          <StatCard 
            title="In Review" 
            value={summary?.inReview} 
            icon={Clock} 
            color="text-amber-500" 
            loading={isSummaryLoading} 
          />
          <StatCard
            title="Invalid"
            value={summary?.invalid}
            icon={XCircle}
            color="text-red-500"
            loading={isSummaryLoading}
          />
          <StatCard
            title="Duplicate"
            value={(summary as any)?.duplicate}
            icon={Copy}
            color="text-fuchsia-500"
            loading={isSummaryLoading}
          />
          <StatCard
            title="Unsupported"
            value={(summary as any)?.unsupported}
            icon={ImageOff}
            color="text-slate-500"
            loading={isSummaryLoading}
          />
          <StatCard
            title="Total Submissions"
            value={summary?.totalSubmissions}
            icon={BarChart3}
            color="text-blue-500"
            loading={isSummaryLoading}
          />
        </div>

        {/* Points breakdown — shows exactly where the total comes from */}
        {summary && (
          <PointsBreakdown
            breakdown={(summary as any).pointsBreakdown}
            total={summary.totalPoints}
          />
        )}

        {/* Recent Submissions */}
        <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
          <div className="p-6 border-b border-border flex justify-between items-center bg-muted/20">
            <h2 className="text-xl font-bold uppercase tracking-wide flex items-center gap-2">
              <Zap size={20} className="text-primary" />
              Recent Intel
            </h2>
          </div>
          
          <div className="p-0">
            {isRecentLoading ? (
              <div className="divide-y divide-border">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="p-4 flex items-center gap-4">
                    <Skeleton className="w-16 h-16 rounded-md bg-muted/50" />
                    <div className="space-y-2 flex-1">
                      <Skeleton className="h-5 w-1/3 bg-muted/50" />
                      <Skeleton className="h-4 w-1/4 bg-muted/50" />
                    </div>
                  </div>
                ))}
              </div>
            ) : recent && recent.length > 0 ? (
              <div className="divide-y divide-border">
                {recent.map((sub) => (
                  <div key={sub.id} className="p-4 flex items-center gap-4 hover:bg-muted/30 transition-colors group">
                    <div className="w-16 h-16 rounded-md overflow-hidden bg-muted border border-border shrink-0 relative">
                      <img src={sub.imageUrl} alt={sub.fileName || "Submission"} className="w-full h-full object-cover" />
                      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <span className="text-[10px] font-bold uppercase tracking-wider">View</span>
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-semibold text-sm truncate">{sub.fileName || "Untitled Submission"}</h4>
                        {sub.platform && (
                          <Badge variant="outline" className="text-[10px] h-5 px-1.5 uppercase font-mono">
                            {sub.platform}
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground font-mono">
                        <span>{format(new Date(sub.createdAt), "MMM d, yyyy HH:mm")}</span>
                        <span className="w-1 h-1 rounded-full bg-border"></span>
                        <span className="text-primary font-bold">+{sub.points} PTS</span>
                      </div>
                    </div>
                    <div>
                      <Badge variant="outline" className={getStatusColor(sub.status)}>
                        {getStatusLabel(sub.status)}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-12 text-center flex flex-col items-center">
                <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4 text-muted-foreground">
                  <Activity size={32} />
                </div>
                <h3 className="text-lg font-bold mb-1">No Intel Found</h3>
                <p className="text-muted-foreground text-sm">Upload your first screenshot to start the grind.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </Shell>
  );
}

type BreakdownEntry = { key: string; label: string; count: number; points: number };

function PointsBreakdown({ breakdown, total }: { breakdown?: BreakdownEntry[]; total?: number }) {
  if (!breakdown || breakdown.length === 0) return null;
  // Only show categories that actually have submissions, ordered as the API returns them.
  const rows = breakdown.filter((b) => b.count > 0);
  if (rows.length === 0) return null;

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm mb-10">
      <div className="p-6 border-b border-border flex items-center justify-between bg-muted/20">
        <h2 className="text-xl font-bold uppercase tracking-wide flex items-center gap-2">
          <Zap size={20} className="text-primary" /> Points Breakdown
        </h2>
        <span className="text-xs text-muted-foreground font-medium">How your total is calculated</span>
      </div>

      <div className="divide-y divide-border">
        {rows.map((b) => {
          const scores = b.points !== 0;
          return (
            <div key={b.key} className="px-6 py-3 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <span className="font-semibold text-sm truncate">{b.label}</span>
                <Badge variant="outline" className="text-[10px] font-mono shrink-0">×{b.count}</Badge>
              </div>
              <span
                className={`font-black font-mono tracking-tight ${
                  b.points > 0 ? "text-green-500" : b.points < 0 ? "text-red-500" : "text-muted-foreground"
                }`}
              >
                {scores ? `${b.points > 0 ? "+" : ""}${b.points.toLocaleString()}` : "0"}
              </span>
            </div>
          );
        })}
      </div>

      <div className="px-6 py-4 flex items-center justify-between bg-muted/20 border-t border-border">
        <span className="text-sm font-bold uppercase tracking-wide">Total Points</span>
        <span className="text-2xl font-black font-mono text-primary tracking-tight">
          {(total ?? 0).toLocaleString()}
        </span>
      </div>

      <p className="px-6 pb-4 pt-1 text-xs text-muted-foreground">
        Each accepted screenshot earns points; duplicate uploads are penalized. Pending submissions
        don&apos;t count until a reviewer approves them. Think a decision is wrong? Use{" "}
        <span className="font-semibold text-foreground">Dispute</span> on the Intel Log.
      </p>
    </div>
  );
}

function StatCard({ title, value, icon: Icon, color, loading }: { title: string, value?: number, icon: any, color: string, loading: boolean }) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 md:p-6 relative overflow-hidden group">
      <div className={`absolute top-0 right-0 p-4 md:p-6 opacity-10 group-hover:opacity-20 transition-opacity ${color}`}>
        <Icon size={48} className="md:hidden" />
        <Icon size={64} className="hidden md:block" />
      </div>
      <h3 className="text-[10px] md:text-sm font-bold text-muted-foreground uppercase tracking-wider mb-1 md:mb-2 leading-tight">{title}</h3>
      {loading ? (
        <Skeleton className="h-8 md:h-10 w-16 md:w-24 bg-muted/50" />
      ) : (
        <div className="text-2xl md:text-4xl font-black font-mono tracking-tighter">
          {value !== undefined ? value.toLocaleString() : "0"}
        </div>
      )}
    </div>
  );
}
