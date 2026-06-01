import { useEffect, useMemo, useState } from "react";
import { Shell } from "@/components/layout/Shell";
import { api, Analytics as AnalyticsData, UserStat } from "@/lib/api";
import { BarChart3, Users as UsersIcon, Ban, CheckCircle2, XCircle, Clock, Zap, FileStack, Copy, ImageOff, ArrowUp, ArrowDown, ArrowUpDown, Wallet } from "lucide-react";

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
  { key: "unsupported", label: "Unsupported", color: "bg-slate-500" },
  { key: "points", label: "Points", color: "bg-primary" },
] as const;

type MetricKey = typeof METRICS[number]["key"];

const TOP_N = 15;

// Sortable columns for the per-user table.
const COLUMNS = [
  { key: "username", label: "User", numeric: false, cls: "font-semibold" },
  { key: "total", label: "Total", numeric: true, cls: "" },
  { key: "accepted", label: "Accepted", numeric: true, cls: "text-green-500" },
  { key: "invalid", label: "Invalid", numeric: true, cls: "text-red-500" },
  { key: "inReview", label: "Review", numeric: true, cls: "text-amber-500" },
  { key: "duplicate", label: "Dup", numeric: true, cls: "text-fuchsia-500" },
  { key: "points", label: "Points", numeric: true, cls: "font-bold text-primary" },
] as const;

type SortKey = typeof COLUMNS[number]["key"];

// Sort users by `key` (asc/desc) with DETERMINISTIC tie-breaks, so equal values always
// render in the same, explainable order: tie -> username A→Z -> userId. Without this, ties
// fall back to whatever order the API returned, which can flip a user in/out of the Top 15.
function sortUsers(rows: UserStat[], key: SortKey | MetricKey, dir: "asc" | "desc"): UserStat[] {
  const sign = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = (a as any)[key];
    const bv = (b as any)[key];
    const primary =
      typeof av === "string" && typeof bv === "string"
        ? av.localeCompare(bv)
        : (av as number) - (bv as number);
    if (primary !== 0) return sign * primary;
    // Deterministic, direction-independent tie-break: username A→Z, then the unique userKey.
    return a.username.localeCompare(b.username) || a.userKey.localeCompare(b.userKey);
  });
}

export default function Analytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [rows, setRows] = useState<UserStat[]>([]);
  const [metric, setMetric] = useState<MetricKey>("total");
  const [sortKey, setSortKey] = useState<SortKey>("total");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.analytics().then(setData).catch((e) => setError(e?.message || "Failed to load"));
    api.userAnalytics().then(setRows).catch(() => {});
  }, []);

  const activeMetric = METRICS.find((m) => m.key === metric)!;
  // Top 15 by the selected metric (fewer if there are fewer users), ties broken deterministically.
  const ranked = useMemo(() => sortUsers(rows, metric, "desc").slice(0, TOP_N), [rows, metric]);
  const max = Math.max(1, ...ranked.map((r) => r[metric] as number));

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      // New column: numeric columns start high→low, the text column starts A→Z.
      const numeric = COLUMNS.find((c) => c.key === key)?.numeric ?? true;
      setSortKey(key);
      setSortDir(numeric ? "desc" : "asc");
    }
  }

  // Top 15 by the chosen table column / direction, same deterministic tie-breaks.
  const tableRows = useMemo(() => sortUsers(rows, sortKey, sortDir).slice(0, TOP_N), [rows, sortKey, sortDir]);

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-6xl mx-auto w-full">
        <div className="mb-8">
          <h1 id="tour-analytics" className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
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
              <Stat title="Total Points" value={data.unsettledPoints ?? data.totalPoints} icon={Zap} color="text-primary" />
              <Stat title="Settled" value={data.settledPoints} icon={Wallet} color="text-emerald-500" />
              <Stat title="Submissions" value={data.totalSubmissions} icon={FileStack} color="text-blue-500" />
              <Stat title="Accepted" value={data.accepted} icon={CheckCircle2} color="text-green-500" />
              <Stat title="Invalid" value={data.invalid} icon={XCircle} color="text-red-500" />
              <Stat title="In Review" value={data.inReview} icon={Clock} color="text-amber-500" />
              <Stat title="Duplicate" value={data.duplicate} icon={Copy} color="text-fuchsia-500" />
              <Stat title="Unsupported" value={data.unsupported} icon={ImageOff} color="text-slate-500" />
              <Stat title="Users" value={data.users} icon={UsersIcon} color="text-primary" />
              <Stat title="Blocked Users" value={data.blockedUsers} icon={Ban} color="text-red-500" />
            </div>

            {/* Per-user breakdown */}
            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
                <h2 className="text-xl font-bold uppercase tracking-wide">By User <span className="text-muted-foreground font-medium normal-case text-sm">· Top {TOP_N} by {activeMetric.label}</span></h2>
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
                      <div key={u.userKey} className="flex items-center gap-3">
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

              {/* Full table — sortable by any column */}
              {tableRows.length > 0 && (
                <div className="mt-8 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs uppercase tracking-wider text-muted-foreground border-b border-border">
                        {COLUMNS.map((c) => {
                          const active = sortKey === c.key;
                          const Arrow = active ? (sortDir === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
                          return (
                            <th
                              key={c.key}
                              className={`py-2 ${c.numeric ? "px-2 text-right" : "pr-4 text-left"}`}
                            >
                              <button
                                onClick={() => toggleSort(c.key)}
                                className={`inline-flex items-center gap-1 uppercase tracking-wider hover:text-foreground transition-colors ${
                                  c.numeric ? "flex-row-reverse" : ""
                                } ${active ? "text-foreground" : ""}`}
                              >
                                {c.label}
                                <Arrow size={12} className={active ? "text-primary" : "opacity-40"} />
                              </button>
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      {tableRows.map((u) => (
                        <tr key={u.userKey} className="border-b border-border/50">
                          {COLUMNS.map((c) => (
                            <td
                              key={c.key}
                              className={`py-2 ${c.numeric ? "px-2 text-right font-mono" : "pr-4"} ${c.cls}`}
                            >
                              {u[c.key]}
                            </td>
                          ))}
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
