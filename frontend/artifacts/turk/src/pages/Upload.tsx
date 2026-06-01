import { useState, useCallback } from "react";
import { Shell } from "@/components/layout/Shell";
import { useUpload } from "@workspace/object-storage-web";
import { useCreateSubmission, getListSubmissionsQueryKey, getGetDashboardSummaryQueryKey, getGetRecentSubmissionsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { UploadCloud, CheckCircle2, AlertCircle, FileImage, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";

interface UploadFileState {
  id: string;
  file: File;
  progress: number;
  status: "pending" | "uploading" | "processing" | "success" | "error";
  error?: string;
}

// Max screenshots that can be queued at once.
const MAX_FILES = 50;

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

  const { uploadFile } = useUpload({
    onSuccess: async (response) => {
      try {
        await createSubmission.mutateAsync({
          data: {
            imageUrl: `/api/storage/objects/${response.objectPath.replace(/^\/objects\//, "")}`,
            objectPath: response.objectPath,
            fileName: response.metadata.name,
            // We could extract platform from filename or let user select, but leaving empty for now
          }
        });
      } catch (err) {
        throw new Error("Failed to create submission record");
      }
    }
  });

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
    let validFiles = incoming.filter(f => f.type.startsWith('image/'));

    if (validFiles.length !== incoming.length) {
      toast({
        title: "Invalid file type",
        description: "Only image files are accepted.",
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
        
        clearInterval(progressInterval);

        if (!result) {
          throw new Error("Upload failed");
        }
        
        // Update to success, then clear the bar from the queue shortly after so
        // only pending/failed items remain visible.
        setFiles(prev => prev.map(f => f.id === fileState.id ? { ...f, status: "success", progress: 100 } : f));
        setTimeout(() => removeFile(fileState.id), 1200);
      } catch (err) {
        // Update to error
        setFiles(prev => prev.map(f => f.id === fileState.id ? { ...f, status: "error", error: "Upload failed" } : f));
      }
    }
    
    toast({
      title: "Operation Complete",
      description: "Finished processing uploads.",
    });
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
                Drop your screenshots here or click to browse. Supported formats: JPG, PNG, WEBP. Up to {MAX_FILES} at a time.
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
                  {files.map((file) => (
                    <div key={file.id} className="bg-card border border-border rounded-lg p-4 flex items-center gap-4">
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
                          <span className="text-xs font-bold uppercase w-16 text-right">
                            {file.status === "pending" && <span className="text-muted-foreground">Ready</span>}
                            {file.status === "uploading" && <span className="text-primary animate-pulse">Up...</span>}
                            {file.status === "success" && <span className="text-green-500">Done</span>}
                            {file.status === "error" && <span className="text-destructive">Err</span>}
                          </span>
                        </div>
                      </div>

                      <div className="shrink-0 pl-2">
                        {file.status === "success" ? (
                          <CheckCircle2 size={20} className="text-green-500" />
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
                  ))}
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
