import { AlertCircle } from "lucide-react";

interface ErrorBannerProps {
  message: string;
}

export const ErrorBanner = ({ message }: ErrorBannerProps) => {
  return (
    <div
      role="alert"
      className="bg-red-50 border border-red-200 text-red-900 p-4 rounded-lg flex items-start gap-3"
    >
      <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" aria-hidden />
      <p className="text-sm leading-relaxed">{message}</p>
    </div>
  );
};

export default ErrorBanner;
