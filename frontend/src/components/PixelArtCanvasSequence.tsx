"use client";

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

export interface PixelArtCanvasSequenceProps {
  frameCount?: number;
  getFrameUrl?: (index: number) => string;
  scrollDistance?: string;
  pixelArtMode?: boolean;
  title?: string;
  subtitle?: string;
  onStartClick?: () => void;
  className?: string;
}

export function PixelArtCanvasSequence({
  frameCount = 146,
  getFrameUrl = (i) => `/sequence/frame_${String(i + 1).padStart(4, "0")}.jpg`,
  scrollDistance = "+=350%",
  pixelArtMode = true,
  title,
  subtitle,
  onStartClick,
  className = "",
}: PixelArtCanvasSequenceProps) {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState(0);
  const [showEndOverlay, setShowEndOverlay] = useState(false);

  const imagesRef = useRef<HTMLImageElement[]>([]);
  const currentFrameRef = useRef({ frame: 0 });

  // 1. Preload sequence frames into memory
  useEffect(() => {
    let isMounted = true;
    let loadedCount = 0;
    const images: HTMLImageElement[] = new Array(frameCount);

    for (let i = 0; i < frameCount; i++) {
      const img = new Image();
      img.src = getFrameUrl(i);

      const handleLoad = () => {
        if (!isMounted) return;
        loadedCount++;
        setLoadProgress(Math.round((loadedCount / frameCount) * 100));
        if (loadedCount === frameCount) {
          setIsLoading(false);
        }
      };

      img.onload = handleLoad;
      img.onerror = handleLoad;

      images[i] = img;
    }

    imagesRef.current = images;

    return () => {
      isMounted = false;
    };
  }, [frameCount, getFrameUrl]);

  // 2. Setup Canvas, aspect-ratio cover scaling (Zero black edges), and GSAP ScrollTrigger
  useEffect(() => {
    if (isLoading || !containerRef.current || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Draw frame to fill canvas 100% (object-fit: cover logic)
    const drawFrame = (frameIndex: number) => {
      const img = imagesRef.current[frameIndex];
      if (!img || !img.complete || img.naturalWidth === 0) return;

      const canvasWidth = canvas.width;
      const canvasHeight = canvas.height;
      const imgWidth = img.naturalWidth;
      const imgHeight = img.naturalHeight;

      // Scale ratio to COVER canvas 100% (takes MAX ratio)
      const scale = Math.max(canvasWidth / imgWidth, canvasHeight / imgHeight);
      
      // Add +4 extra pixels to guarantee 0 subpixel edge rounding seams on any monitor
      const drawWidth = Math.ceil(imgWidth * scale) + 4;
      const drawHeight = Math.ceil(imgHeight * scale) + 4;

      // Center crop
      const offsetX = Math.floor((canvasWidth - drawWidth) / 2);
      const offsetY = Math.floor((canvasHeight - drawHeight) / 2);

      if (pixelArtMode) {
        ctx.imageSmoothingEnabled = false;
      } else {
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
      }

      ctx.clearRect(0, 0, canvasWidth, canvasHeight);
      ctx.drawImage(img, offsetX, offsetY, drawWidth, drawHeight);
    };

    // Responsive Canvas Resize with Retina high-DPI scaling
    const handleResize = () => {
      const dpr = Math.max(window.devicePixelRatio || 1, 1);
      const width = window.innerWidth;
      const height = window.innerHeight;

      canvas.width = Math.ceil(width * dpr);
      canvas.height = Math.ceil(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      drawFrame(Math.round(currentFrameRef.current.frame));
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    drawFrame(0);

    // GSAP ScrollTrigger Timeline
    const frameState = { frame: 0 };
    currentFrameRef.current = frameState;

    const ctxGsap = gsap.context(() => {
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          pin: true,
          scrub: 1, // Smooth physics scrubbing
          start: "top top",
          end: scrollDistance,
          onUpdate: (self) => {
            const index = Math.min(
              frameCount - 1,
              Math.max(0, Math.round(frameState.frame)),
            );
            drawFrame(index);

            // Reveal the NEURO 16-bit transparent logo header & CTA button at end
            if (self.progress >= 0.85) {
              setShowEndOverlay(true);
            } else {
              setShowEndOverlay(false);
            }
          },
        },
      });

      tl.to(frameState, {
        frame: frameCount - 1,
        ease: "none",
      });
    }, containerRef);

    return () => {
      window.removeEventListener("resize", handleResize);
      ctxGsap.revert();
    };
  }, [isLoading, frameCount, scrollDistance, pixelArtMode]);

  const handleStart = () => {
    if (onStartClick) {
      onStartClick();
    } else {
      navigate("/intake");
    }
  };

  return (
    <div
      ref={containerRef}
      className={`relative w-screen h-screen m-0 p-0 overflow-hidden bg-black ${className}`}
      style={{
        position: "relative",
        width: "100vw",
        height: "100vh",
        margin: 0,
        padding: 0,
        overflow: "hidden",
        backgroundColor: "#000000",
      }}
    >
      {/* Preloader Overlay */}
      {isLoading && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            width: "100vw",
            height: "100vh",
            zIndex: 50,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#000000",
            color: "#ffffff",
            fontFamily: "monospace",
          }}
        >
          <div
            className="neuro-spinner"
            style={{
              width: "4rem",
              height: "4rem",
              border: "4px solid rgba(250, 204, 21, 0.3)",
              borderTopColor: "#facc15",
              borderRadius: "50%",
              marginBottom: "1.5rem",
            }}
          />
          <p
            style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              letterSpacing: "0.1em",
              color: "#facc15",
              marginBottom: "0.5rem",
              fontFamily: "'Press Start 2P', 'Pixelify Sans', monospace",
            }}
          >
            LOADING NEURO...
          </p>
          <p style={{ fontSize: "0.875rem", color: "#a1a1aa", fontFamily: "monospace", marginBottom: "1rem" }}>
            {loadProgress}%
          </p>
          <div
            style={{
              width: "16rem",
              height: "0.75rem",
              backgroundColor: "#18181b",
              border: "1px solid rgba(250, 204, 21, 0.4)",
              borderRadius: "2px",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                backgroundColor: "#facc15",
                width: `${loadProgress}%`,
                transition: "width 150ms ease-out",
              }}
            />
          </div>
        </div>
      )}

      {/* HTML5 Canvas (Full-bleed 100vw x 100vh) */}
      <canvas
        ref={canvasRef}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100vw",
          height: "100vh",
          objectFit: "cover",
          display: "block",
          margin: 0,
          padding: 0,
          border: "none",
          zIndex: 0,
          touchAction: "none",
        }}
      />

      {/* Scroll Down Cue (Visible while scrubbing sequence) */}
      {!isLoading && !showEndOverlay && (
        <div
          style={{
            position: "fixed",
            bottom: "2rem",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 20,
            pointerEvents: "none",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <span
            style={{
              fontSize: "0.75rem",
              fontWeight: "bold",
              letterSpacing: "0.1em",
              color: "#fde047",
              filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.9))",
              textTransform: "uppercase",
              fontFamily: "'Press Start 2P', monospace",
            }}
          >
            SCROLL TO EXPLORE
          </span>
          <svg
            className="neuro-bounce"
            style={{
              width: "1.5rem",
              height: "1.5rem",
              color: "#facc15",
              filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.9))",
            }}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={3}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
        </div>
      )}

      {/* Centered End Reveal Overlay: Transparent 16-Bit NEURO Logo Header & CTA Button */}
      <div
        className="neuro-end-overlay"
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          width: "100vw",
          height: "100vh",
          zIndex: 30,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "1.5rem",
          textAlign: "center",
          boxSizing: "border-box",
          transition: "all 700ms cubic-bezier(0.16, 1, 0.3, 1)",
          backgroundColor: showEndOverlay ? "rgba(0, 0, 0, 0.4)" : "transparent",
          backdropFilter: showEndOverlay ? "blur(3px)" : "none",
          WebkitBackdropFilter: showEndOverlay ? "blur(3px)" : "none",
          opacity: showEndOverlay ? 1 : 0,
          transform: showEndOverlay ? "scale(1)" : "scale(0.92)",
          pointerEvents: showEndOverlay ? "auto" : "none",
        }}
      >
        {/* Transparent 16-Bit NEURO Logo Heading Header (Centered) */}
        <div
          className="neuro-logo-anim"
          style={{
            marginBottom: subtitle ? "1.5rem" : "2.5rem",
            width: "100%",
            maxWidth: "650px",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <img
            src="/neuro-logo.png"
            alt={title || "NEURO"}
            style={{
              width: "100%",
              maxWidth: "650px",
              height: "auto",
              maxHeight: "35vh",
              objectFit: "contain",
              userSelect: "none",
              pointerEvents: "none",
              imageRendering: "pixelated",
              filter:
                "drop-shadow(0 0 25px rgba(255, 230, 0, 0.75)) drop-shadow(0 12px 35px rgba(0, 0, 0, 0.9))",
            }}
          />
        </div>

        {/* Tagline (Only rendered if custom subtitle is provided) */}
        {subtitle && (
          <p
            style={{
              fontSize: "clamp(0.875rem, 2vw, 1.25rem)",
              color: "#fde047",
              fontWeight: "bold",
              maxWidth: "42rem",
              marginBottom: "2.5rem",
              letterSpacing: "0.08em",
              filter: "drop-shadow(0 4px 12px rgba(0,0,0,0.95))",
              textTransform: "uppercase",
              fontFamily: "'Press Start 2P', 'Pixelify Sans', monospace",
              lineHeight: 1.6,
            }}
          >
            {subtitle}
          </p>
        )}

        {/* 16-Bit Retro Arcade CTA Button */}
        <button
          onClick={handleStart}
          style={{
            fontFamily: "'Press Start 2P', monospace",
            backgroundColor: "#000000",
            color: "#FFE600",
            border: "4px solid #FFE600",
            boxShadow: "6px 6px 0px #000000, 0 0 25px rgba(255, 230, 0, 0.5)",
            display: "inline-flex",
            alignItems: "center",
            gap: "1rem",
            padding: "1.25rem 2rem",
            fontSize: "clamp(0.875rem, 1.5vw, 1.25rem)",
            fontWeight: "bold",
            textTransform: "uppercase",
            cursor: "pointer",
            transition: "all 200ms ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "#FFE600";
            e.currentTarget.style.color = "#000000";
            e.currentTarget.style.borderColor = "#FFFFFF";
            e.currentTarget.style.boxShadow =
              "8px 8px 0px #000000, 0 0 35px rgba(255, 255, 255, 0.7)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "#000000";
            e.currentTarget.style.color = "#FFE600";
            e.currentTarget.style.borderColor = "#FFE600";
            e.currentTarget.style.boxShadow =
              "6px 6px 0px #000000, 0 0 25px rgba(255, 230, 0, 0.5)";
          }}
        >
          <span>START INTAKE</span>
          <span style={{ fontSize: "1.25em" }}>▶</span>
        </button>
      </div>
    </div>
  );
}

export default PixelArtCanvasSequence;
