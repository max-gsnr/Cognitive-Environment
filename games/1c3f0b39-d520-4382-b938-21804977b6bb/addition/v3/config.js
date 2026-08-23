// Static config. The game is served from the same origin as the Orbit API
// (FastAPI mounts the games directory at /games), so API_BASE is empty by
// default. Override with ?api=http://localhost:8000 when serving elsewhere.
window.ORBIT = (function () {
  const params = new URLSearchParams(window.location.search);
  const override = params.get("api");
  return {
    API_BASE: (override !== null ? override : window.ORBIT_API_BASE || "").replace(
      /\/$/,
      ""
    ),
    GAME_ID: "337551d8-1d90-4491-94f5-b35485fb86ca",
    PROFILE_ID: "1c3f0b39-d520-4382-b938-21804977b6bb",
    SKILL_ID: "addition",
    VERSION: 3,
    SESSION_LENGTH: 10,
    POSTHOG_KEY: "phc_zQYVxHgoH7FV7RZGhVQRNcsWpVA6mRAgh2UvW9dW25tc",
    POSTHOG_HOST: "https://eu.i.posthog.com",

    // Straight from the child's profile. Every effect below is gated on these;
    // nothing decorative is on by default.
    CONSTRAINTS: {
      visual: {
        color_palette: "pastel_muted",
        animations: "minimal_no_screen_shake",
        particle_effects: false,
      },
      audio: { music: false, sfx: "ui_only" },
      cognitive: {
        timer: "disabled",
        ui_clutter: "single_focal_point",
        level_length: "micro",
        reward_frequency: "instant_per_action",
      },
      emotional: {
        error_feedback: "gentle_no_red_x",
        fail_state: "impossible_to_lose",
      },
    },
  };
})();
