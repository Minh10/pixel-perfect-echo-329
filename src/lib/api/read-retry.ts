import { ApiError } from "./http-service";

/** Known proxy failures need an explicit retry, not repeated background requests. */
export function retryDocumentRead(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError) return false;
  return failureCount < 1;
}