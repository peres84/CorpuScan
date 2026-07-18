import { useState, useCallback } from "react";
import { Upload, X, FileText, CheckSquare } from "lucide-react";

interface FileUploadProps {
  onSubmit: (files: File[], priorityFiles: string[]) => void;
  isLoading: boolean;
  error: string | null;
}

const SUPPORTED_EXTENSIONS = [".txt", ".pdf", ".xlsx", ".csv", ".docx", ".xml"];

const FileUpload = ({ onSubmit, isLoading, error }: FileUploadProps) => {
  const [files, setFiles] = useState<File[]>([]);
  const [priorityFiles, setPriorityFiles] = useState<Set<string>>(new Set());
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      SUPPORTED_EXTENSIONS.some((ext) => f.name.toLowerCase().endsWith(ext))
    );
    setFiles((prev) => [...prev, ...dropped]);
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files).filter((f) =>
        SUPPORTED_EXTENSIONS.some((ext) => f.name.toLowerCase().endsWith(ext))
      );
      setFiles((prev) => [...prev, ...selected]);
    }
  };

  const removeFile = (index: number) => {
    const fileName = files[index].name;
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setPriorityFiles((prev) => {
      const next = new Set(prev);
      next.delete(fileName);
      return next;
    });
  };

  const togglePriority = (fileName: string) => {
    setPriorityFiles((prev) => {
      const next = new Set(prev);
      if (next.has(fileName)) {
        next.delete(fileName);
      } else {
        next.add(fileName);
      }
      return next;
    });
  };

  const handleSubmit = () => {
    if (files.length === 0) return;
    onSubmit(files, Array.from(priorityFiles));
  };

  return (
    <div className="space-y-6">
      {/* Drop zone */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
          dragActive
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/50"
        }`}
      >
        <Upload className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
        <p className="text-lg font-medium text-foreground mb-1">
          Drop documents here
        </p>
        <p className="text-sm text-muted-foreground mb-4">
          Supports: {SUPPORTED_EXTENSIONS.join(", ")}
        </p>
        <label className="inline-block px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground cursor-pointer hover:bg-primary/90">
          Browse Files
          <input
            type="file"
            multiple
            accept={SUPPORTED_EXTENSIONS.join(",")}
            onChange={handleFileInput}
            className="hidden"
          />
        </label>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-foreground">
              {files.length} file{files.length !== 1 ? "s" : ""} selected
            </h3>
            <p className="text-xs text-muted-foreground">
              Check files to mark as priority (optional)
            </p>
          </div>

          <div className="space-y-1 max-h-64 overflow-y-auto">
            {files.map((file, idx) => (
              <div
                key={`${file.name}-${idx}`}
                className="flex items-center gap-3 px-3 py-2 rounded-md bg-muted/50"
              >
                <button
                  type="button"
                  onClick={() => togglePriority(file.name)}
                  className={`flex-shrink-0 ${
                    priorityFiles.has(file.name)
                      ? "text-primary"
                      : "text-muted-foreground"
                  }`}
                  title="Mark as priority"
                >
                  <CheckSquare className="h-4 w-4" />
                </button>
                <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <span className="text-sm text-foreground flex-1 truncate">
                  {file.name}
                </span>
                <span className="text-xs text-muted-foreground">
                  {(file.size / 1024).toFixed(0)} KB
                </span>
                <button
                  type="button"
                  onClick={() => removeFile(idx)}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <button
            onClick={handleSubmit}
            disabled={isLoading || files.length === 0}
            className="w-full px-4 py-3 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? "Starting Investigation..." : "Start Investigation"}
          </button>
        </div>
      )}
    </div>
  );
};

export default FileUpload;
