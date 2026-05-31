import { useEffect, useMemo, useState } from "react";
import { Shell } from "@/components/layout/Shell";
import { api, Analytics as AnalyticsData, UserStat } from "@/lib/api";
import { BarChart3, Users as UsersIcon, Ban, CheckCircle2, XCircle, Clock, Zap, FileStack, Copy } from "lucide-react";

function Stat({ title, value, icon: Icon, color }: { title: string; value?: number; icon: any; color: string }) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 relative overflow-hidden group">
      <div className={`absolute top-0 right-0 p-6 opacity-10 group-hover:opacity-20 transition-opacity ${color}`}>
        <Icon size={64} />
      </div>
      <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider mb-2">{title}</h3>
      <div className="text-4xl font-black font-mono tracking-tighter">{(value ?? 0).toLocaleString()}</div>
    </div>
  );
}

const METRICS = [
  { key: "total", label: "Submissions", color: "bg-blue-500" },
  { key: "accepted", label: "Accepted", color: "bg-green-500" },
  { key: "invalid", label: "Invalid", color: "bg-red-500" },
  { key: "inReview", label: "In Review", color: "bg-amber-500" },
  { key: "duplicate", label: "Duplicate", color: "bg-fuchsia-500" },
  { key: "points", label: "Points", color: "bg-primary" },
] as const;

type MetricKey = typeof METRICS[number]["key"];

export default function Analytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [rows, setRows] = useState<UserStat[]>([]);
  const [metric, setMetric] = useState<MetricKey>("total");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.analytics().then(setData).catch((e) => setError(e?.message || "Failed to load"));
    api.userAnalytics().then(setRows).catch(() => {});
  }, []);

  const activeMetric = METRICS.find((m) => m.key === metric)!;
  const ranked = useMemo(
    () => [...rows].sort((a, b) => (b[metric] as number) - (a[metric] as number)),
    [rows, metric],
  );
  const max = Math.max(1, ...ranked.map((r) => r[metric] as number));

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-6xl mx-auto w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
            <BarChart3 className="text-primary" /> Analytics
          </h1>
          <p className="text-muted-foreground font-medium">
            {data?.scope === "platform"
              ? "Platform-wide stats."
              : `Stats for ${data?.orgName || "your organization"}.`}
          </p>
        </div>

        {error ? (
          <p className="text-destructive">{error}</p>
        ) : !data ? (
          <p className="text-muted-foreground">Loading…</p>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
              <Stat title="Total Points" value={data.totalPoints} icon={Zap} color="text-primary" />
              <Stat title="Submissions" value={data.totalSubmissions} icon={FileStack} color="text-blue-500" />
              <Stat title="Accepted" value={data.accepted} icon={CheckCircle2} color="text-green-500" />
              <Stat title="Invalid" value={data.invalid} icon={XCircle} color="text-red-500" />
              <Stat title="In Review" value={data.inReview} icon={Clock} color="text-amber-500" />
              <Stat title="Duplicate" value={data.duplicate} icon={Copy} color="text-fuchsia-500" />
              <Stat title="Users" value={data.users} icon={UsersIcon} color="text-primary" />
              <Stat title="Blocked Users" value={data.blockedUsers} icon={Ban} color="text-red-500" />
            </div>

            {/* Per-user breakdown */}
            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
                <h2 className="text-xl font-bold uppercase tracking-wide">By User</h2>
                <div className="flex flex-wrap gap-1.5">
                  {METRICS.map((m) => (
                    <button
                      key={m.key}
                      onClick={() => setMetric(m.key)}
                      className={`text-xs font-bold uppercase tracking-wider px-3 py-1.5 rounded-md border transition-colors ${
                        metric === m.key
                          ? "bg-primary/10 text-primary border-primary/30"
                          : "border-border text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>

              {ranked.length === 0 ? (
                <p className="text-muted-foreground text-sm">No submissions yet.</p>
              ) : (
                <div className="space-y-3">
                  {ranked.map((u, i) => {
                    const v = u[metric] as number;
                    return (
                      <div key={u.userId} className="flex items-center gap-3">
                        <div className="w-40 shrink-0 flex items-center gap-2 min-w-0">
                          <span className="text-xs font-mono text-muted-foreground w-5">#{i + 1}</span>
                          <span className="text-sm font-semibold truncate">{u.username}</span>
                        </div>
                        <div className="flex-1 h-6 bg-muted/40 rounded overflow-hidden">
                          <div
                            className={`h-full ${activeMetric.color} transition-all`}
                            style={{ width: `${(v / max) * 100}%` }}
                          />
                        </div>
                        <span className="w-12 text-right text-sm font-mono font-bold">{v.toLocaleString()}</span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Full table */}
              {ranked.length > 0 && (
                <div className="mt-8 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground border-b border-border">
                        <th className="py-2 pr-4">User</th>
                        <th className="py-2 px-2 text-right">Total</th>
                        <th className="py-2 px-2 text-right">Accepted</th>
                        <th className="py-2 px-2 text-right">Invalid</th>
                        <th className="py-2 px-2 text-right">Review</th>
                        <th className="py-2 px-2 text-right">Dup</th>
                        <th className="py-2 pl-2 text-right">Points</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ranked.map((u) => (
                        <tr key={u.userId} className="border-b border-border/50">
                          <td className="py-2 pr-4 font-semibold">{u.username}</td>
                          <td className="py-2 px-2 text-right font-mono">{u.total}</td>
                          <td className="py-2 px-2 text-right font-mono text-green-500">{u.accepted}</td>
                          <td className="py-2 px-2 text-right font-mono text-red-500">{u.invalid}</td>
                          <td className="py-2 px-2 text-right font-mono text-amber-500">{u.inReview}</td>
                          <td className="py-2 px-2 text-right font-mono text-fuchsia-500">{u.duplicate}</td>
                          <td className="py-2 pl-2 text-right font-mono font-bold text-primary">{u.points}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
