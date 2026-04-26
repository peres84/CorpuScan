import { Link } from "react-router-dom";
import { Download } from "lucide-react";

interface JobResultProps {
  videoUrl: string;
}

export const JobResult = ({ videoUrl }: JobResultProps) => {
  const downloadUrl = new URL(videoUrl);
  downloadUrl.searchParams.set("download", "1");

  return (
    <div>
      <video
        controls
        src={videoUrl}
        className="w-full rounded-lg bg-primary"
        preload="metadata"
      >
        Your browser does not support the video tag.
      </video>

      <div className="mt-6 flex flex-col sm:flex-row gap-3">
        <a
          href={downloadUrl.toString()}
          download
          className="inline-flex items-center justify-center gap-2 bg-accent text-accent-foreground rounded-lg px-5 py-3 font-medium hover:bg-accent/90 transition-colors"
        >
          <Download className="h-4 w-4" aria-hidden />
          Download MP4
        </a>
        <Link
          to="/dashboard"
          className="inline-flex items-center justify-center border border-border text-primary rounded-lg px-5 py-3 font-medium hover:bg-muted transition-colors"
        >
          Generate another
        </Link>
      </div>
    </div>
  );
};

export default JobResult;
