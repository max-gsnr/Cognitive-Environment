import { PixelArtCanvasSequence } from "../components/PixelArtCanvasSequence";


export function PixelArtSequencePage() {
  return (
    <div style={{ width: "100%", background: "#09090b", minHeight: "100vh" }}>
      {/* Pinned ScrollTrigger Canvas Section */}
      <PixelArtCanvasSequence
        frameCount={146}
        getFrameUrl={(i) => `/sequence/frame_${String(i + 1).padStart(4, "0")}.jpg`}
        scrollDistance="+=400%"
        title="Pixel Art Animation Sequence"
        subtitle="Scroll down to play frame-by-frame on HTML5 Canvas • Scrub up to reverse"
        pixelArtMode={true}
      />

      {/* Content Section below pinned animation */}
      <div className="max-w-4xl mx-auto px-6 py-24 text-white">
        <h2 className="text-3xl font-bold mb-4">GSAP ScrollTrigger Canvas Architecture</h2>
        <p className="text-zinc-400 text-lg leading-relaxed mb-6">
          This component preloads the image sequence into memory and synchronizes drawing onto an HTML5 Canvas using GSAP&apos;s ScrollTrigger pin and scrub mechanics. 
          Dynamic device pixel ratio (Retina) scaling and aspect-ratio cover math ensure crisp, responsive rendering without layout shifts or black bars.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-8">
          <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-xl">
            <h3 className="text-emerald-400 font-semibold mb-2">Preloaded Memory</h3>
            <p className="text-zinc-400 text-sm">All 146 frames are pre-buffered before ScrollTrigger binds, guaranteeing 60 FPS performance.</p>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-xl">
            <h3 className="text-indigo-400 font-semibold mb-2">Scrub & Pin</h3>
            <p className="text-zinc-400 text-sm">Container remains pinned while scrub physics ties animation progress directly to scroll depth.</p>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-xl">
            <h3 className="text-purple-400 font-semibold mb-2">Responsive Cover</h3>
            <p className="text-zinc-400 text-sm">Canvas aspect-ratio scaling automatically crops and covers the viewport upon window resize.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PixelArtSequencePage;
