// Static config for Leo's Orbit game
window.ORBIT = (function () {
  const params = new URLSearchParams(window.location.search);
  const override = params.get("api");
  return {
    API_BASE: (override !== null ? override : window.ORBIT_API_BASE || "").replace(
      /\/$/,
      ""
    ),
    GAME_ID: "leo-space-docking-v2",
    PROFILE_ID: "ec9f2ef3-c7df-46a1-96d2-fa77130fcc2a",
    SKILL_ID: "addition",
    VERSION: 2,
    SESSION_LENGTH: 5,
    POSTHOG_KEY: "phc_orbit_mock_key",
    POSTHOG_HOST: "https://us.i.posthog.com",
    CONSTRAINTS: {
      visual: { color_palette: "high_contrast_calm", animations: "standard", particle_effects: true },
      audio: { sfx: "ui_only", music: false },
      cognitive: { timer: "disabled", ui_clutter: "single_focal_point" },
      emotional: { fail_state: "impossible_to_lose", error_feedback: "gentle_no_red_x" }
    }
  };
})();
