// Static config for neopapi's Token Machine. The rendering shell knows the ids
// and the profile constraints; it knows nothing about difficulty.
window.ORBIT = (function () {
  const params = new URLSearchParams(window.location.search);
  const override = params.get("api");
  return {
    API_BASE: (override !== null ? override : window.ORBIT_API_BASE || "").replace(
      /\/$/,
      ""
    ),
    GAME_ID: "5cc8073c-f673-46ff-842f-890b6e4627a9",
    PROFILE_ID: "f458f038-c28b-4bf4-96a6-0345b565c5ae",
    SKILL_ID: "addition",
    VERSION: 1,
    SESSION_LENGTH: 10,
    POSTHOG_KEY: "",
    POSTHOG_HOST: "https://us.i.posthog.com",
    CONSTRAINTS: {
      visual: {
        color_palette: "pastel_muted",
        animations: "standard",
        particle_effects: true,
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
