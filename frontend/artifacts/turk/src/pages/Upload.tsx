import { useState, useCallback, useEffect, useRef } from "react";
import { Shell } from "@/components/layout/Shell";
import { useUpload } from "@workspace/object-storage-web";
import { useCreateSubmission, getListSubmissionsQueryKey, getGetDashboardSummaryQueryKey, getGetRecentSubmissionsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { UploadCloud, CheckCircle2, AlertCircle, FileImage, X, Clock, Copy, XCircle, ImageOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";

// Per-upload verdict returned by the backend, with its display treatment.
type Verdict = "accepted" | "in_review" | "duplicate" | "invalid" | "unsupported";

const VERDICT: Record<Verdict, { label: string; Icon: any; text: string; ring: string }> = {
  accepted:    { label: "Accepted",    Icon: CheckCircle2, text: "text-green-500",   ring: "border-green-500/50 shadow-[0_0_22px_rgba(34,197,94,0.30)]" },
  in_review:   { label: "In review",   Icon: Clock,        text: "text-amber-500",   ring: "border-amber-500/50 shadow-[0_0_22px_rgba(245,158,11,0.30)]" },
  duplicate:   { label: "Duplicate",   Icon: Copy,         text: "text-fuchsia-500", ring: "border-fuchsia-500/50 shadow-[0_0_22px_rgba(217,70,239,0.30)]" },
  invalid:     { label: "Invalid",     Icon: XCircle,      text: "text-red-500",     ring: "border-red-500/50 shadow-[0_0_22px_rgba(239,68,68,0.30)]" },
  unsupported: { label: "Unsupported", Icon: ImageOff,     text: "text-slate-400",   ring: "border-slate-500/50 shadow-[0_0_22px_rgba(100,116,139,0.30)]" },
};

const CONFETTI_COLORS = [
  "#22c55e", "#16a34a", "#4ade80", "#a3e635", "#84cc16", "#06b6d4",
  "#22d3ee", "#38bdf8", "#3b82f6", "#6366f1", "#a855f7", "#c084fc",
  "#d946ef", "#ec4899", "#f43f5e", "#f59e0b", "#fbbf24", "#fde047",
  "#fb923c", "#ffffff",
];
const CONFETTI_SIZES = [5, 6, 7, 8, 9, 10, 11, 12, 14];
// Mixed shapes for a fuller, varied burst (clip-paths + radii applied per particle).
const STAR = "polygon(50% 0%,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)";
const TRI = "polygon(50% 0%, 0% 100%, 100% 100%)";
const DIAMOND = "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)";
const SHAPES = ["circle", "square", "rect", "triangle", "star", "diamond", "circle", "rect"] as const;

// Lightweight, dependency-free confetti — a full, dense fountain burst (upward fan + gravity
// fall) of many colours, sizes and shapes, via the Web Animations API. Mounted only for
// accepted uploads; self-cleaning (~1.8s). Particles overflow the row frame.
function ConfettiBurst({ count = 90 }: { count?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    (Array.from(root.children) as HTMLElement[]).forEach((p) => {
      // Fan mostly upward for a fountain, then let "gravity" pull each piece back down.
      const angle = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.3;
      const power = 70 + Math.random() * 150;
      const dx = Math.cos(angle) * power;
      const dyUp = Math.sin(angle) * power;          // negative = upward
      const fall = 140 + Math.random() * 200;        // gravity drop on the way out
      const rot = Math.random() * 1200 - 600;
      const dur = 950 + Math.random() * 800;
      p.animate(
        [
          { transform: "translate(0,0) rotate(0deg) scale(1)", opacity: 1, offset: 0 },
          { transform: `translate(${dx * 0.6}px, ${dyUp}px) rotate(${rot * 0.5}deg) scale(1)`, opacity: 1, offset: 0.35 },
          { transform: `translate(${dx}px, ${dyUp + fall}px) rotate(${rot}deg) scale(0.6)`, opacity: 0, offset: 1 },
        ],
        { duration: dur, easing: "cubic-bezier(.15,.6,.3,1)", fill: "forwards" },
      );
    });
  }, []);
  return (
    <div ref={ref} aria-hidden className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center overflow-visible">
      {Array.from({ length: count }).map((_, i) => {
        const shape = SHAPES[i % SHAPES.length];
        const size = CONFETTI_SIZES[(i * 3) % CONFETTI_SIZES.length];
        const color = CONFETTI_COLORS[(i * 7) % CONFETTI_COLORS.length];
        let w = size, h = size;
        const st: React.CSSProperties = { background: color };
        if (shape === "circle") st.borderRadius = "50%";
        else if (shape === "square") st.borderRadius = 1;
        else if (shape === "rect") { w = Math.max(3, Math.round(size * 0.5)); h = Math.round(size * 2.6); st.borderRadius = 1; } // streamer
        else if (shape === "triangle") st.clipPath = TRI;
        else if (shape === "star") { w = Math.round(size * 1.5); h = w; st.clipPath = STAR; }
        else if (shape === "diamond") st.clipPath = DIAMOND;
        return <span key={i} className="absolute" style={{ ...st, width: w, height: h }} />;
      })}
    </div>
  );
}

// Celebratory "+N" that pops out of the row, bounces (scale overshoot) and keeps
// growing as it flies up and out of frame — paired with the confetti on an accept.
function PointsPop({ label }: { label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.animate(
      [
        { transform: "translate(-50%,-50%) translateY(0) scale(0.3)", opacity: 0, offset: 0 },
        { transform: "translate(-50%,-50%) translateY(-8px) scale(1.5)", opacity: 1, offset: 0.28 },   // pop + overshoot
        { transform: "translate(-50%,-50%) translateY(-16px) scale(1.15)", opacity: 1, offset: 0.46 }, // bounce settle
        { transform: "translate(-50%,-50%) translateY(-82px) scale(2.5)", opacity: 0, offset: 1 },      // grow + fly out of frame
      ],
      { duration: 1400, easing: "cubic-bezier(.2,.8,.25,1)", fill: "forwards" },
    );
  }, []);
  return (
    <div
      ref={ref}
      aria-hidden
      className="pointer-events-none absolute left-1/2 top-1/2 z-30 font-black tracking-tight text-green-400 drop-shadow-[0_0_12px_rgba(34,197,94,0.85)]"
      style={{ fontSize: 30 }}
    >
      {label}
    </div>
  );
}

interface UploadFileState {
  id: string;
  file: File;
  progress: number;
  status: "pending" | "uploading" | "processing" | "done" | "error";
  verdict?: Verdict;
  points?: number;
  leaving?: boolean;
  error?: string;
}

// Max screenshots that can be queued at once.
const MAX_FILES = 50;
// Per-image size cap (keep in sync with backend MAX_UPLOAD_MB).
const MAX_FILE_MB = 10;
const MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024;

export default function Upload() {
  const [files, setFiles] = useState<UploadFileState[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const createSubmission = useCreateSubmission({
    mutation: {
      onSuccess: () => {
        // Invalidate queries to refresh data
        queryClient.invalidateQueries({ queryKey: getListSubmissionsQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetDashboardSummaryQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetRecentSubmissionsQueryKey() });
      }
    }
  });

  // Upload to storage only; the submission record is created in the loop so we can read
  // the result (and surface duplicates).
  const { uploadFile } = useUpload();

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const processFiles = (newFiles: FileList | File[]) => {
    const incoming = Array.from(newFiles);
    const images = incoming.filter(f => f.type.startsWith('image/'));

    if (images.length !== incoming.length) {
      toast({
        title: "Invalid file type",
        description: "Only image files are accepted.",
        variant: "destructive"
      });
    }

    // Reject anything over the per-image size cap.
    let validFiles = images.filter(f => f.size <= MAX_FILE_BYTES);
    if (validFiles.length !== images.length) {
      toast({
        title: "Image too large",
        description: `Each image must be ${MAX_FILE_MB} MB or smaller; ${images.length - validFiles.length} skipped.`,
        variant: "destructive"
      });
    }

    // Cap the queue at MAX_FILES screenshots at a time.
    const capacity = MAX_FILES - files.length;
    if (capacity <= 0) {
      toast({
        title: "Upload limit reached",
        description: `You can queue at most ${MAX_FILES} screenshots at a time.`,
        variant: "destructive"
      });
      return;
    }
    if (validFiles.length > capacity) {
      toast({
        title: "Upload limit reached",
        description: `Only ${capacity} more can be added (max ${MAX_FILES}); ${validFiles.length - capacity} skipped.`,
        variant: "destructive"
      });
      validFiles = validFiles.slice(0, capacity);
    }

    if (validFiles.length > 0) {
      const newFileStates: UploadFileState[] = validFiles.map(file => ({
        id: Math.random().toString(36).substring(7),
        file,
        progress: 0,
        status: "pending"
      }));
      setFiles(prev => [...prev, ...newFileStates]);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFiles(e.dataTransfer.files);
    }
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFiles(e.target.files);
    }
    // Reset input so the same files can be selected again if needed
    e.target.value = '';
  };

  const removeFile = (id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id));
  };

  const startUploads = async () => {
    const pendingFiles = files.filter(f => f.status === "pending" || f.status === "error");

    if (pendingFiles.length === 0) return;

    for (const fileState of pendingFiles) {
      // Update status to uploading
      setFiles(prev => prev.map(f => f.id === fileState.id ? { ...f, status: "uploading", progress: 10 } : f));
      
      try {
        // Simulate progress for UI since useUpload's progress isn't easily mapped per-file in this loop
        const progressInterval = setInterval(() => {
          setFiles(prev => prev.map(f => {
            if (f.id === fileState.id && f.progress < 90) {
              return { ...f, progress: f.progress + 10 };
            }
            return f;
          }));
        }, 300);

        const result = await uploadFile(fileState.file);

        if (!result) {
          clearInterval(progressInterval);
          throw new Error("Upload failed");
        }

        // Create the submission record and read the verdict so we can flag duplicates.
        const created: any = await createSubmission.mutateAsync({
          data: {
            imageUrl: `/api/storage/objects/${result.objectPath.replace(/^\/objects\//, "")}`,
            objectPath: result.objectPath,
            fileName: result.metadata.name,
          },
        });
        clearInterval(progressInterval);

        // Surface the actual verdict (accepted / in_review / duplicate / invalid /
        // unsupported) on the row, then pulse it out: hold ~2.4s so the user sees
        // the result + confetti for accepts, then fade + collapse the row away.
        const verdict = ((created?.status as Verdict) ?? "accepted");
        setFiles(prev => prev.map(f => f.id === fileState.id
          ? { ...f, status: "done", progress: 100, verdict, points: created?.points }
          : f));
        setTimeout(() => {
          setFiles(prev => prev.map(f => f.id === fileState.id ? { ...f, leaving: true } : f));
          setTimeout(() => removeFile(fileState.id), 360);
        }, 2400);
      } catch (err) {
        // Update to error
        setFiles(prev => prev.map(f => f.id === fileState.id ? { ...f, status: "error", error: "Upload failed" } : f));
      }
    }
    
    // No toasts — confetti + the per-row verdict (incl. fuchsia "Duplicate" rows)
    // already convey the outcome.
  };

  const pendingCount = files.filter(f => f.status === "pending" || f.status === "error").length;
  const isUploading = files.some(f => f.status === "uploading" || f.status === "processing");

  return (
    <Shell>
      <div className="flex-1 p-6 md:p-8 max-w-5xl mx-auto w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-black uppercase tracking-tight">Upload Screenshots</h1>
          <p className="text-muted-foreground font-medium">
            Upload mobile screenshots of <span className="text-foreground font-semibold">verified accounts of
            African-descent creators</span> to process and earn points.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div
              id="tour-dropzone"
              className={cn(
                "border-2 border-dashed rounded-xl p-6 md:p-12 flex flex-col items-center justify-center text-center transition-all duration-200 relative overflow-hidden",
                isDragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 bg-card",
                isUploading ? "pointer-events-none opacity-50" : "cursor-pointer"
              )}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <input 
                type="file" 
                multiple 
                accept="image/*" 
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={handleFileInput}
                disabled={isUploading}
              />
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center text-primary mb-4 shadow-[0_0_15px_rgba(0,255,255,0.2)]">
                <UploadCloud size={32} />
              </div>
              <h3 className="text-xl font-bold mb-2">Drag & Drop Screenshots</h3>
              <p className="text-muted-foreground max-w-sm">
                Drop your screenshots here or click to browse. Supported formats: JPG, PNG, WEBP. Up to {MAX_FILES} at a time, max {MAX_FILE_MB} MB each.
              </p>
            </div>

            {files.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold uppercase tracking-wide">Queue ({files.length})</h3>
                  {pendingCount > 0 && (
                    <Button 
                      onClick={startUploads} 
                      disabled={isUploading}
                      className="font-bold uppercase tracking-wide bg-primary text-primary-foreground hover:bg-primary/90 shadow-[0_0_15px_rgba(0,255,255,0.3)]"
                    >
                      {isUploading ? "Processing..." : `Process ${pendingCount} files`}
                    </Button>
                  )}
                </div>

                <div className="space-y-3">
                  {files.map((file) => {
                    const v = file.status === "done" && file.verdict ? VERDICT[file.verdict] : undefined;
                    const showConfetti = file.status === "done" && file.verdict === "accepted" && !file.leaving;
                    return (
                    <div
                      key={file.id}
                      className={cn(
                        "relative bg-card border rounded-lg p-4 flex items-center gap-4 transition-all duration-300",
                        v ? v.ring : "border-border",
                        file.leaving ? "opacity-0 scale-95" : "opacity-100",
                      )}
                    >
                      {showConfetti && <ConfettiBurst />}
                      {showConfetti && file.points ? <PointsPop label={`+${file.points}`} /> : null}
                      <div className="w-12 h-12 rounded bg-muted flex items-center justify-center shrink-0">
                        <FileImage size={24} className="text-muted-foreground" />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-center mb-1">
                          <h4 className="font-semibold text-sm truncate pr-4">{file.file.name}</h4>
                          <span className="text-xs font-mono text-muted-foreground shrink-0">
                            {(file.file.size / 1024 / 1024).toFixed(2)} MB
                          </span>
                        </div>

                        <div className="flex items-center gap-3">
                          <div className="flex-1">
                            <Progress value={file.progress} className="h-1.5" />
                          </div>
                          <span className="text-[10px] font-bold uppercase leading-tight w-24 text-right whitespace-nowrap">
                            {file.status === "pending" && <span className="text-muted-foreground">Ready</span>}
                            {file.status === "uploading" && <span className="text-primary animate-pulse">Up...</span>}
                            {v && (
                              <span className={v.text}>
                                {file.verdict === "accepted" && file.points ? `+${file.points} pts` : v.label}
                              </span>
                            )}
                            {file.status === "error" && <span className="text-destructive">Err</span>}
                          </span>
                        </div>
                      </div>

                      <div className="shrink-0 pl-2">
                        {v ? (
                          <v.Icon size={20} className={v.text} />
                        ) : file.status === "error" ? (
                          <AlertCircle size={20} className="text-destructive" />
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground hover:text-destructive"
                            onClick={() => removeFile(file.id)}
                            disabled={isUploading && file.status !== "pending"}
                          >
                            <X size={16} />
                          </Button>
                        )}
                      </div>
                    </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-1">
            <div className="bg-card border border-border rounded-xl p-6 sticky top-24">
              <h3 className="text-lg font-bold uppercase tracking-wide mb-4 flex items-center gap-2">
                <AlertCircle size={18} className="text-primary" />
                Guidelines
              </h3>
              <ul className="space-y-4 text-sm text-muted-foreground">
                <li className="flex gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>Ensure your username is clearly visible in the screenshot.</span>
                </li>
                <li className="flex gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>Metrics (likes, views, retweets) must be uncropped.</span>
                </li>
                <li className="flex gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>Duplicate submissions will be automatically rejected.</span>
                </li>
                <li className="flex gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>Manipulated images will result in account termination.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
