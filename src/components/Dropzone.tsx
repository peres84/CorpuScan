import { useCallback, useRef, useState } from "react";
import { FileText, X } from "lucide-react";

interface DropzoneProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const Dropzone = ({ file, onFileChange }: DropzoneProps) => {
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSelect = useCallback(
    (f: File | null) => {
      if (!f) {
        onFileChange(null);
        return;
      }
      if (!f.name.toLowerCase().endsWith(".pdf") && f.type !== "application/pdf") {
        return;
      }
      onFileChange(f);
    },
    [onFileChange],
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);
      const f = e.dataTransfer.files?.[0] ?? null;
      handleSelect(f);
    },
    [handleSelect],
  );

  if (file) {
    return (
      <div className="border border-border rounded-lg p-4 flex items-center justify-between bg-muted/40">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-10 w-10 rounded-md bg-accent/10 text-accent flex items-center justify-center shrink-0">
            <FileText className="h-5 w-5" aria-hidden />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-primary truncate">{file.name}</p>
            <p className="text-xs text-secondary font-mono">{formatBytes(file.size)}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => onFileChange(null)}
          className="text-secondary hover:text-primary text-sm inline-flex items-center gap-1 shrink-0 ml-4"
        >
          <X className="h-4 w-4" aria-hidden />
          Remove
        </button>
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      role="button"
      tabIndex={0}
      className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
        isDragOver ? "border-accent bg-accent/5" : "border-border hover:border-accent hover:bg-accent/5"
      }`}
    >
      <p className="text-primary font-medium">Drop your PDF here</p>
      <p className="mt-1 text-sm text-secondary">or click to browse</p>
      <p className="mt-4 text-xs text-secondary font-mono">PDF only</p>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        onChange={(e) => handleSelect(e.target.files?.[0] ?? null)}
      />
    </div>
  );
};

export default Dropzone;
