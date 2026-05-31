import { useEffect, useState, useCallback } from "react";
import { Shell } from "@/components/layout/Shell";
import { api, ReviewItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle2, XCircle, RefreshCw, ShieldCheck } from "lucide-react";

export default function ReviewQueue() {
  const { toast } = useToast();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.reviewQueue(1, 50);
      setItems(data.items);
    } catch (e: any) {
      toast({ title: "Failed to load queue", description: e?.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (id: number, kind: "approve" | "reject" | "rerun") => {
    setBusyId(id);
    try {
      const res: any = await api[kind](id);
      toast({ title: `Done: ${kind}`, description: `Submission #${id} → ${res?.status ?? "updated"}` });
      // approve/reject leave the queue; rerun may keep it if still in_review.
      if (kind === "rerun" && res?.status === "in_review") {
        await load();
      } else {
        setItems((prev) => prev.filter((i) => i.id !== id));
      }
    } catch (e: any) {
      toast({ title: `Failed to ${kind}`, description: e?.message, variant: "destructive" });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-5xl mx-auto w-full">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
              <ShieldCheck className="text-primary" /> Review Queue
            </h1>
            <p className="text-muted-foreground font-medium">Borderline submissions awaiting a human decision.</p>
          </div>
          <Button variant="outline" onClick={load} className="gap-2"><RefreshCw size={16} /> Refresh</Button>
        </div>

        {loading ? (
          <p className="text-muted-foreground">Loading…</p>
        ) : items.length === 0 ? (
          <div className="p-12 text-center bg-card border border-border rounded-xl">
            <CheckCircle2 size={40} className="mx-auto text-green-500 mb-3" />
            <h3 className="text-lg font-bold">Queue clear</h3>
            <p className="text-muted-foreground text-sm">No submissions are waiting for review.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((it) => (
              <div key={it.id} className="bg-card border border-border rounded-xl p-4 flex flex-col md:flex-row gap-4">
                <div className="w-full md:w-48 h-48 rounded-lg overflow-hidden bg-muted border border-border shrink-0">
                  <img src={it.imageUrl} alt={it.fileName || "submission"} className="w-full h-full object-cover" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-bold truncate">#{it.id} · {it.fileName || "Untitled"}</h3>
                    {it.platform && <Badge variant="outline" className="uppercase font-mono text-[10px]">{it.platform}</Badge>}
                  </div>
                  <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm mb-3 font-mono">
                    <span className="text-muted-foreground">AI verified</span>
                    <span className={it.verified ? "text-green-500" : "text-red-500"}>{String(it.verified)}</span>
                    <span className="text-muted-foreground">Confidence</span>
                    <span>{it.confidence != null ? `${Math.round(it.confidence * 100)}%` : "—"}</span>
                    <span className="text-muted-foreground">Handle</span>
                    <span className="truncate">{it.profile?.handle || "—"}</span>
                  </div>
                  {it.reasoning && (
                    <p className="text-xs text-muted-foreground italic mb-3 line-clamp-2">“{it.reasoning}”</p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" disabled={busyId === it.id} onClick={() => act(it.id, "approve")}
                      className="gap-1 bg-green-600 hover:bg-green-600/90 text-white"><CheckCircle2 size={15} /> Approve</Button>
                    <Button size="sm" disabled={busyId === it.id} onClick={() => act(it.id, "reject")}
                      variant="outline" className="gap-1 border-destructive/40 text-destructive hover:bg-destructive/10"><XCircle size={15} /> Reject</Button>
                    <Button size="sm" disabled={busyId === it.id} onClick={() => act(it.id, "rerun")}
                      variant="outline" className="gap-1"><RefreshCw size={15} /> Re-run AI</Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Shell>
  );
}
