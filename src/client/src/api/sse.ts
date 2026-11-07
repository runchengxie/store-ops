export type SseEvent =
  | { type: "phase"; phase: string }
  | { type: "attempt"; provider: string }
  | { type: "token"; text: string; provider: string }
  | { type: "error"; detail: string }
  | { type: "done"; provider: string; elapsed_s: number };

export async function consumeSSE(
  resp: Response,
  onEvent: (evt: SseEvent) => void,
): Promise<void> {
  const reader = resp.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith(":")) continue;
      if (trimmed.startsWith("data:")) {
        try {
          const evt = JSON.parse(trimmed.slice(5).trim());
          onEvent(evt);
        } catch { /* ignore */ }
      }
    }
  }
}
