import { useEffect, useState, useCallback } from "react";
import { Shell } from "@/components/layout/Shell";
import { api, ReviewItem, SubmissionPreview } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle2, XCircle, RefreshCw, ShieldCheck, ImageOff, Maximize2, X, ExternalLink, Sparkles } from "lucide-react";

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

// One review card. Shows the stored AI details first; only auto-runs the AI when there are no
// details yet. "Run AI" re-fetches details WITHOUT deciding the verdict. The reviewer confirms
// or types the handle (required) and then Approves — approval is never automatic.
function ReviewCard({
  item, onResolved, onOpenImage,
}: {
  item: ReviewItem;
  onResolved: (id: number) => void;
  onOpenImage: (url: string, name: string) => void;
}) {
  const { toast } = useToast();
  const storedHandle = item.profile?.handle || "";
  const hasStored = item.verified != null || !!storedHandle || !!item.reasoning;

  const [d, setD] = useState<SubmissionPreview>({
    platform: item.platform,
    verified: item.verified,
    confidence: item.confidence,
    africanClass: item.africanClass,
    accountType: item.accountType,
    name: item.profile?.display_name || item.profile?.name,
    handle: storedHandle || undefined,
    reasoning: item.reasoning,
  });
  const [handle, setHandle] = useState(storedHandle);
  const [busy, setBusy] = useState<null | "approve" | "reject" | "ai">(null);
  const [ranAI, setRanAI] = useState(false);

  const runAI = useCallback(async () => {
    setBusy("ai");
    try {
      const p = await api.previewSubmission(item.id);
      setD((prev) => ({ ...prev, ...p }));
      if (p.handle) setHandle(p.handle);
      setRanAI(true);
    } catch (e: any) {
      toast({ title: "Run AI failed", description: e?.message, variant: "destructive" });
    } finally {
      setBusy(null);
    }
  }, [item.id, toast]);

  // Auto-run ONLY when there are no stored details yet; otherwise show what we have.
  useEffect(() => {
    if (!hasStored) runAI();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const approve = async () => {
    const h = handle.trim();
    if (!h) return;
    setBusy("approve");
    try {
      const res: any = await api.approve(item.id, { acctHandle: h, acctPlatform: d.platform || item.platform });
      toast({ title: "Approved", description: `#${item.id} → ${res?.status ?? "accepted"} (@${h})` });
      onResolved(item.id);
    } catch (e: any) {
      toast({ title: "Approve failed", description: e?.message, variant: "destructive" });
      setBusy(null);
    }
  };

  const reject = async () => {
    setBusy("reject");
    try {
      await api.reject(item.id);
      toast({ title: "Rejected", description: `#${item.id} → invalid` });
      onResolved(item.id);
    } catch (e: any) {
      toast({ title: "Reject failed", description: e?.message, variant: "destructive" });
      setBusy(null);
    }
  };

  const isBusy = busy !== null;
  return (
    <div className={`relative bg-card border border-border rounded-xl p-4 flex flex-col md:flex-row gap-4 transition-opacity ${isBusy ? "opacity-60" : ""}`}>
      <Thumb src={item.imageUrl} alt={item.fileName || "submission"} onOpen={() => onOpenImage(item.imageUrl, item.fileName || "submission")} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <h3 className="font-bold truncate">#{item.id} · {item.fileName || "Untitled"}</h3>
          {d.platform && <Badge variant="outline" className="uppercase font-mono text-[10px]">{d.platform}</Badge>}
          {item.disputed && (
            <Badge variant="destructive" className="uppercase font-mono text-[10px]"
              title="The owner contested a decided verdict — this was sent back for review">Disputed</Badge>
          )}
          {ranAI && <Badge variant="secondary" className="text-[10px] gap-1"><Sparkles size={11} /> AI refreshed</Badge>}
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm mb-3 font-mono">
          <span className="text-muted-foreground">AI verified</span>
          <span className={d.verified ? "text-green-500" : "text-red-500"}>{String(d.verified ?? "—")}</span>
          <span className="text-muted-foreground">Confidence</span>
          <span>{d.confidence != null ? `${Math.round(d.confidence * 100)}%` : "—"}</span>
          <span className="text-muted-foreground">Name</span>
          <span className="truncate">{d.name || "—"}</span>
          <span className="text-muted-foreground">Account type</span>
          <span className="capitalize">{d.accountType || "—"}</span>
          <span className="text-muted-foreground">African</span>
          <span className={d.africanClass === "african" ? "text-green-500" : d.africanClass === "non_african" ? "text-red-500" : "text-muted-foreground"}>
            {(d.africanClass || "unclear").replace("_", "-")}
          </span>
        </div>
        {d.reasoning && <p className="text-xs text-muted-foreground italic mb-3 line-clamp-2">“{d.reasoning}”</p>}

        {/* Handle is the dedup key — required to approve, editable, pre-filled from the AI. */}
        <div className="mb-3">
          <label className="text-xs text-muted-foreground font-medium">Captured handle (required to approve)</label>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-muted-foreground font-mono">@</span>
            <Input
              value={handle}
              onChange={(e) => setHandle(e.target.value.replace(/^@/, ""))}
              placeholder="username"
              disabled={isBusy}
              className="max-w-xs font-mono"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={isBusy || !handle.trim()} onClick={approve}
            title={!handle.trim() ? "Enter a handle first" : "Approve as a verified capture"}
            className="gap-1 bg-green-600 hover:bg-green-600/90 text-white">
            <CheckCircle2 size={15} /> {busy === "approve" ? "Approving…" : "Approve"}
          </Button>
          <Button size="sm" disabled={isBusy} onClick={reject}
            variant="outline" className="gap-1 border-destructive/40 text-destructive hover:bg-destructive/10">
            <XCircle size={15} /> {busy === "reject" ? "Rejecting…" : "Reject"}
          </Button>
          <Button size="sm" disabled={isBusy} onClick={runAI} variant="outline" className="gap-1">
            <RefreshCw size={15} className={busy === "ai" ? "animate-spin" : ""} />
            {busy === "ai" ? "Running…" : "Run AI"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function ReviewQueue() {
  const { toast } = useToast();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
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

  useEffect(() => { load(); }, [load]);

  const onResolved = useCallback((id: number) => setItems((prev) => prev.filter((i) => i.id !== id)), []);

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-5xl mx-auto w-full">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 id="tour-review-queue" className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
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
              <ReviewCard
                key={it.id}
                item={it}
                onResolved={onResolved}
                onOpenImage={(url, name) => setPreview({ url, name })}
              />
            ))}
          </div>
        )}
      </div>

      {/* Full-image lightbox */}
      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={() => setPreview(null)}>
          <div className="relative max-w-4xl max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
            <img src={preview.url} alt={preview.name} className="max-w-full max-h-[90vh] rounded-lg object-contain shadow-2xl" />
            <div className="absolute top-2 right-2 flex gap-2">
              <a href={preview.url} target="_blank" rel="noopener noreferrer" title="Open original in new tab"
                className="w-9 h-9 rounded-full bg-black/60 hover:bg-black/80 text-white flex items-center justify-center transition-colors">
                <ExternalLink size={16} />
              </a>
              <button onClick={() => setPreview(null)} title="Close"
                className="w-9 h-9 rounded-full bg-black/60 hover:bg-black/80 text-white flex items-center justify-center transition-colors">
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
