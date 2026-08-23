import posthog from "posthog-js";

const key = import.meta.env.VITE_POSTHOG_KEY;
let ready = false;

if (key) {
  posthog.init(key, {
    api_host: import.meta.env.VITE_POSTHOG_HOST ?? "https://us.i.posthog.com",
    capture_pageview: false,
  });
  ready = true;
}

/** Telemetry is observational only -- nothing in the game reads it back. */
export function capture(event: string, properties: Record<string, unknown>) {
  if (ready) {
    posthog.capture(event, properties);
  }
}
