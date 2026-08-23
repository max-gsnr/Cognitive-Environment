import React, { useEffect, useRef, useState } from "react";
import { AttemptResult, Question } from "../api";
import { OpenGameArena, THEMES, getThemeForInterests } from "./OpenGameArena";

interface OrbitCanvasProps {
  profileId: string;
  skillId: string;
  interests?: string[];
  sessionLength?: number;
  onQuestionLoaded?: (q: Question) => void;
  onAttemptResult?: (result: AttemptResult) => void;
  onScoreUpdate?: (score: number, answered: number) => void;
  onLevelComplete?: () => void;
}

export const OrbitCanvas: React.FC<OrbitCanvasProps> = ({
  profileId,
  skillId,
  interests = [],
  sessionLength = 10,
  onQuestionLoaded,
  onAttemptResult,
  onScoreUpdate,
  onLevelComplete,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const gameRef = useRef<OpenGameArena | null>(null);

  // Initialize theme based on the child's interests
  const initialThemeKey = Object.keys(THEMES).find(
    (k) => THEMES[k].name === getThemeForInterests(interests).name
  ) || "nebula";

  const [selectedTheme, setSelectedTheme] = useState<string>(initialThemeKey);
  const [audioEnabled, setAudioEnabled] = useState<boolean>(true);
  const [inputVal, setInputVal] = useState<string>("");
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const autoKey = Object.keys(THEMES).find(
      (k) => THEMES[k].name === getThemeForInterests(interests).name
    ) || "nebula";
    setSelectedTheme(autoKey);
  }, [interests]);

  useEffect(() => {
    if (!canvasRef.current) return;

    const game = new OpenGameArena(
      canvasRef.current,
      profileId,
      skillId,
      {
        onQuestionLoaded,
        onAttemptResult,
        onScoreUpdate,
        onLevelComplete,
      },
      selectedTheme
    );

    game.sessionLength = sessionLength;
    game.setAudio(audioEnabled);
    game.startLoop();
    gameRef.current = game;

    return () => {
      game.destroy();
      gameRef.current = null;
    };
  }, [profileId, skillId, sessionLength, selectedTheme]);

  const handleAudioToggle = () => {
    const next = !audioEnabled;
    setAudioEnabled(next);
    gameRef.current?.setAudio(next);
  };

  const handleKeypadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    const num = Number(inputVal);
    if (!isNaN(num)) {
      gameRef.current?.submitAnswer(num);
      setInputVal("");
    }
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen?.().then(() => setIsFullscreen(true));
    } else {
      document.exitFullscreen?.().then(() => setIsFullscreen(false));
    }
  };

  return (
    <div ref={containerRef} className="orbit-game-container">
      {/* Top Game Controls Bar (Distraction-Free: Sound & Fullscreen only) */}
      <div className="game-toolbar" style={{ justifyContent: "flex-end" }}>
        <div className="toolbar-actions">
          <button
            type="button"
            className="pill-btn"
            onClick={handleAudioToggle}
            aria-label="Toggle Sound"
          >
            {audioEnabled ? "🔊 Sound ON" : "🔇 Sound OFF"}
          </button>
          <button
            type="button"
            className="pill-btn"
            onClick={toggleFullscreen}
            aria-label="Toggle Fullscreen"
          >
            {isFullscreen ? "🗗 Window" : "⛶ Fullscreen"}
          </button>
        </div>
      </div>

      {/* Canvas Viewport */}
      <div className="canvas-wrapper">
        <canvas ref={canvasRef} className="orbit-canvas" />
      </div>

      {/* Fast Input Bar / Keypad for Accessibility & Hybrid Play */}
      <div className="game-bottom-bar">
        <form onSubmit={handleKeypadSubmit} className="hybrid-keypad-form">
          <label htmlFor="quick-input" className="keypad-label">
            Math Coordinates:
          </label>
          <input
            id="quick-input"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={4}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value.replace(/[^0-9]/g, ""))}
            placeholder="Type answer..."
            className="keypad-input"
            autoFocus
          />
          <button type="submit" className="primary keypad-submit" disabled={!inputVal}>
            Dock (Enter)
          </button>
        </form>

        <div className="controls-legend">
          <span>🚀 <strong>Glide:</strong> Click / Tap Canvas</span>
          <span>✦ <strong>Dock:</strong> Type Coordinates & Enter</span>
        </div>
      </div>
    </div>
  );
};
