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
    GAME_ID: "5a49f04f-47c9-4738-949c-5b1046517088",
    PROFILE_ID: "1c3f0b39-d520-4382-b938-21804977b6bb",
    SKILL_ID: "addition",
    VERSION: 2,
    SESSION_LENGTH: 10,
    POSTHOG_KEY: "phc_zQYVxHgoH7FV7RZGhVQRNcsWpVA6mRAgh2UvW9dW25tc",
    POSTHOG_HOST: "https://us.i.posthog.com",
  };
})();
