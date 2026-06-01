import { useEffect, useState } from "react";
import { Shell } from "@/components/layout/Shell";
import { api, Invoice, InvoiceDetail, OutstandingSummary } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { format } from "date-fns";
import { Receipt, FilePlus2, CheckCircle2 } from "lucide-react";

const money = (amt: number, cur: string) =>
  `${cur} ${amt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const statusBadge = (status: string) =>
  status === "settled"
    ? "bg-green-500/10 text-green-500 border-green-500/20"
    : "bg-amber-500/10 text-amber-500 border-amber-500/20";

export default function Invoices() {
  const { toast } = useToast();
  const { isSuperuser } = useAuth();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [outstanding, setOutstanding] = useState<OutstandingSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [detail, setDetail] = useState<InvoiceDetail | null>(null);
  const [open, setOpen] = useState(false);

  const load = () => {
    api.listInvoices().then(setInvoices).catch(() => {});
    if (!isSuperuser) api.invoiceOutstanding().then(setOutstanding).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const generate = async () => {
    setBusy(true);
    try {
      const inv = await api.generateInvoice();
      toast({ title: "Invoice generated", description: `#${inv.id}: ${inv.submissionCount} items, ${inv.totalPoints} pts.` });
      load();
    } catch (e: any) {
      toast({ title: "Failed", description: e?.message, variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  const openDetail = async (id: number) => {
    setOpen(true);
    setDetail(null);
    try {
      setDetail(await api.getInvoice(id));
    } catch (e: any) {
      toast({ title: "Failed", description: e?.message, variant: "destructive" });
    }
  };

  const settle = async (id: number) => {
    setBusy(true);
    try {
      await api.settleInvoice(id);
      toast({ title: "Invoice settled" });
      setOpen(false);
      load();
    } catch (e: any) {
      toast({ title: "Failed", description: e?.message, variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-5xl mx-auto w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-black uppercase tracking-tight flex items-center gap-2">
            <Receipt className="text-primary" /> Invoices
          </h1>
          <p className="text-muted-foreground font-medium">
            {isSuperuser ? "Review and settle organization invoices." : "Generate invoices for your outstanding points."}
          </p>
        </div>

        {/* Org admin: outstanding + generate */}
        {!isSuperuser && outstanding && (
          <div className="bg-card border border-primary/20 rounded-xl p-6 mb-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex gap-6 sm:gap-10">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Outstanding</div>
                <div className="text-2xl font-black font-mono">{outstanding.count}<span className="text-sm text-muted-foreground"> subs</span></div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Points</div>
                <div className="text-2xl font-black font-mono">{outstanding.points.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Amount</div>
                <div className="text-2xl font-black font-mono text-primary">{money(outstanding.amount, outstanding.currency)}</div>
              </div>
            </div>
            <Button disabled={busy || outstanding.count === 0} onClick={generate} className="gap-2 font-bold uppercase tracking-wide shrink-0">
              <FilePlus2 size={16} /> Generate invoice
            </Button>
          </div>
        )}

        {/* Invoice list */}
        <div className="bg-card border border-border rounded-xl divide-y divide-border overflow-hidden">
          {invoices.length === 0 ? (
            <p className="p-6 text-muted-foreground text-sm">No invoices yet.</p>
          ) : (
            invoices.map((inv) => (
              <button
                key={inv.id}
                onClick={() => openDetail(inv.id)}
                className="w-full p-4 flex items-center justify-between gap-3 hover:bg-muted/20 text-left transition-colors"
              >
                <div className="min-w-0">
                  <p className="font-semibold">
                    Invoice #{inv.id}
                    {isSuperuser && inv.orgName ? <span className="text-muted-foreground font-normal"> · {inv.orgName}</span> : null}
                  </p>
                  <p className="text-xs text-muted-foreground font-mono">
                    {inv.submissionCount} items · {inv.totalPoints} pts · {format(new Date(inv.createdAt), "MMM d, yyyy")}
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="font-black font-mono text-sm">{money(inv.amount, inv.currency)}</span>
                  <Badge variant="outline" className={`uppercase text-[10px] ${statusBadge(inv.status)}`}>{inv.status}</Badge>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Detail dialog */}
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogTitle className="uppercase tracking-wide text-sm flex items-center gap-2">
              <Receipt size={16} /> Invoice {detail ? `#${detail.id}` : ""}
            </DialogTitle>
            {!detail ? (
              <p className="text-muted-foreground text-sm py-6">Loading…</p>
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
                  <div><span className="text-muted-foreground">Org:</span> <b>{detail.orgName || detail.orgId}</b></div>
                  <div><span className="text-muted-foreground">Points:</span> <b>{detail.totalPoints}</b></div>
                  <div>
                    <span className="text-muted-foreground">Amount:</span>{" "}
                    <b className="text-primary">{money(detail.amount, detail.currency)}</b>{" "}
                    <span className="text-xs text-muted-foreground">({detail.rate}/pt)</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Status:</span>{" "}
                    <Badge variant="outline" className={`uppercase text-[10px] ${statusBadge(detail.status)}`}>{detail.status}</Badge>
                  </div>
                </div>

                <div className="border border-border rounded-lg overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                      <tr>
                        <th className="text-left p-2">#</th>
                        <th className="text-left p-2">User</th>
                        <th className="text-left p-2">Platform</th>
                        <th className="text-left p-2">Handle</th>
                        <th className="text-left p-2">Status</th>
                        <th className="text-right p-2">Pts</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {detail.items.map((it) => (
                        <tr key={it.id}>
                          <td className="p-2 font-mono text-xs">{it.id}</td>
                          <td className="p-2 truncate max-w-[120px]">{it.username || it.userId}</td>
                          <td className="p-2">{it.platform || "—"}</td>
                          <td className="p-2 font-mono text-xs">{it.handle ? `@${it.handle}` : "—"}</td>
                          <td className="p-2 uppercase text-xs">{it.status}</td>
                          <td className="p-2 text-right font-mono">{it.points}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {isSuperuser && detail.status === "pending" && (
                  <Button disabled={busy} onClick={() => settle(detail.id)} className="w-full gap-2 bg-green-600 hover:bg-green-600/90 text-white font-bold uppercase tracking-wide">
                    <CheckCircle2 size={16} /> Settle invoice
                  </Button>
                )}
                {detail.status === "settled" && (
                  <p className="text-sm text-green-500 flex items-center gap-2">
                    <CheckCircle2 size={16} /> Settled
                    {detail.settledAt ? ` on ${format(new Date(detail.settledAt), "MMM d, yyyy")}` : ""}
                    {detail.settledBy ? ` by ${detail.settledBy}` : ""}.
                  </p>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </Shell>
  );
}
