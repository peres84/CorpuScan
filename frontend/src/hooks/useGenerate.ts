import { useCallback, useState } from "react";
import { postGenerate, type GenerateInput } from "@/lib/api";

interface UseGenerateState {
  loading: boolean;
  error: string | null;
}

export function useGenerate() {
  const [state, setState] = useState<UseGenerateState>({ loading: false, error: null });

  const mutate = useCallback(async (input: GenerateInput): Promise<{ jobId: string }> => {
    setState({ loading: true, error: null });
    try {
      const { job_id } = await postGenerate(input);
      setState({ loading: false, error: null });
      return { jobId: job_id };
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setState({ loading: false, error: message });
      throw err;
    }
  }, []);

  return { mutate, ...state };
}
