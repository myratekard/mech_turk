import { useEffect, useState, useCallback } from "react";
import { Shell } from "@/components/layout/Shell";
import { api, ReviewItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle2, XCircle, RefreshCw, ShieldCheck, ImageOff, Maximize2, X, ExternalLink } from "lucide-react";

// Thumbnail that opens the full image on click and degrades gracefully when the
// source can't be loaded (e.g. legacy rows with a missing/placeholder image_url).
function Thumb({ src, alt, onOpen }: { src?: string; alt: string; onOpen: () => void }) {
  const [broken, setBroken] = useState(false);
  const canOpen = !!src && !broken;
  return (
    <button
      type="button"
      onClick={canOpen ? onOpen : undefined}
      title={canOpen ? "Click to view full image" : "Preview unavailable"}
      className={`group relative w-full md:w-48 h-48 rounded-lg overflow-hidden bg-muted border border-border shrink-0 ${canOpen ? "cursor-zoom-in" : "cursor-default"}`}
    >
      {!src || broken ? (
        <div className="w-full h-full flex flex-col items-center justify-center text-muted-foreground gap-1.5">
          <ImageOff size={28} />
          <span className="text-[11px] font-medium">Preview unavailable</span>
        </div>
      ) : (
        <>
          <img src={src} alt={alt} className="w-full h-full object-cover" onError={() => setBroken(true)} />
          <span className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/40 opacity-0 group-hover:opacity-100 transition-all">
            <Maximize2 size={22} className="text-white" />
          </span>
        </>
      )}
    </button>
  );
}

export default function ReviewQueue() {
  const { toast } = useToast();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<{ id: number; kind: "approve" | "reject" | "rerun" } | null>(null);
  const [preview, setPreview] = useState<{ url: string; name: string } | null>(null);

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
    setBusy({ id, kind });
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
      setBusy(null);
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
            {items.map((it) => {
              const isBusy = busy?.id === it.id;
              return (
              <div
                key={it.id}
                className={`relative bg-card border border-border rounded-xl p-4 flex flex-col md:flex-row gap-4 transition-opacity ${
                  isBusy ? "opacity-50 pointer-events-none" : ""
                }`}
              >
                {isBusy && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center gap-2 text-sm font-semibold text-muted-foreground">
                    <RefreshCw size={18} className="animate-spin text-primary" />
                    {busy?.kind === "rerun" ? "Re-running AI…" : busy?.kind === "approve" ? "Approving…" : "Rejecting…"}
                  </div>
                )}
                <Thumb
                  src={it.imageUrl}
                  alt={it.fileName || "submission"}
                  onOpen={() => setPreview({ url: it.imageUrl, name: it.fileName || "submission" })}
                />
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
                    <Button size="sm" disabled={isBusy} onClick={() => act(it.id, "approve")}
                      className="gap-1 bg-green-600 hover:bg-green-600/90 text-white"><CheckCircle2 size={15} /> Approve</Button>
                    <Button size="sm" disabled={isBusy} onClick={() => act(it.id, "reject")}
                      variant="outline" className="gap-1 border-destructive/40 text-destructive hover:bg-destructive/10"><XCircle size={15} /> Reject</Button>
                    <Button size="sm" disabled={isBusy} onClick={() => act(it.id, "rerun")}
                      variant="outline" className="gap-1">
                      <RefreshCw size={15} className={isBusy && busy?.kind === "rerun" ? "animate-spin" : ""} />
                      {isBusy && busy?.kind === "rerun" ? "Re-running…" : "Re-run AI"}
                    </Button>
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Full-image lightbox */}
      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setPreview(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
            <img
              src={preview.url}
              alt={preview.name}
              className="max-w-full max-h-[90vh] rounded-lg object-contain shadow-2xl"
            />
            <div className="absolute top-2 right-2 flex gap-2">
              <a
                href={preview.url}
                target="_blank"
                rel="noopener noreferrer"
                title="Open original in new tab"
                className="w-9 h-9 rounded-full bg-black/60 hover:bg-black/80 text-white flex items-center justify-center transition-colors"
              >
                <ExternalLink size={16} />
              </a>
              <button
                onClick={() => setPreview(null)}
                title="Close"
                className="w-9 h-9 rounded-full bg-black/60 hover:bg-black/80 text-white flex items-center justify-center transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            <p className="mt-2 text-center text-xs text-white/70 font-mono truncate">{preview.name}</p>
          </div>
        </div>
      )}
    </Shell>
  );
}
