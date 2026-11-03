import { useEffect, useState } from "react";

/** `value`, but only after it has stopped changing for `delayMs`. Every change restarts the timer (cleanup cancels the old one). */
export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}
