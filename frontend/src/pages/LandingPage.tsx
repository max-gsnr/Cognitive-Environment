import { PixelArtCanvasSequence } from "../components/PixelArtCanvasSequence";

export function LandingPage() {
  return (
    <div style={{ width: "100vw", minHeight: "100vh", margin: 0, padding: 0, overflowX: "hidden", background: "#000" }}>
      <PixelArtCanvasSequence
        frameCount={58}
        getFrameUrl={(i) => `/sequence/frame_${String(i + 1).padStart(4, "0")}.jpg`}
        scrollDistance="+=350%"
        pixelArtMode={true}
      />
    </div>
  );
}

export default LandingPage;
