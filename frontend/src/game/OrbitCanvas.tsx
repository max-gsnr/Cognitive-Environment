import React, { useEffect, useRef, useState } from "react";
import { AttemptResult, Question } from "../api";
import { OpenGameArena, THEMES, getThemeForInterests } from "./OpenGameArena";

interface OrbitCanvasProps {
  profileId: string;
  skillId: string;
  interests?: string[];
  sessionLength?: number;
  /** The live generated build, stamped onto each attempt for release comparison. */
  gameId?: string | null;
  gameVersion?: number | null;
  onQuestionLoaded?: (q: Question) => void;
  onAttemptResult?: (result: AttemptResult) => void;
  onScoreUpdate?: (score: number, answered: number) => void;
  onLevelComplete?: () => void;
}

export const OrbitCanvas: React.FC<OrbitCanvasProps> = ({
  profileId,
  skillId,
  interests = [],
  sessionLength = 5,
  gameId = null,
  gameVersion = null,
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

  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const game = new OpenGameArena(
      canvasRef.current,
      profileId,
      skillId,
      {
        onQuestionLoaded: (q: Question) => {
          setCurrentQuestion(q);
          onQuestionLoaded?.(q);
        },
        onAttemptResult,
        onScoreUpdate,
        onLevelComplete,
      },
      selectedTheme
    );

    game.sessionLength = sessionLength;
    game.gameId = gameId;
    game.gameVersion = gameVersion;
    game.setAudio(audioEnabled);
    game.startLoop();
    gameRef.current = game;

    return () => {
      game.destroy();
      gameRef.current = null;
    };
  }, [profileId, skillId, sessionLength, selectedTheme, gameId, gameVersion]);

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

      {/* Centered Bottom Input Bar with High-Visibility Math Challenge */}
      <div className="game-bottom-bar">
        <form onSubmit={handleKeypadSubmit} className="hybrid-keypad-form">
          <div className="math-equation-badge" aria-label="Math Question">
            <span className="math-label">SOLVE:</span>
            <span className="math-equation">
              {currentQuestion
                ? `${currentQuestion.operands[0]} ${currentQuestion.operator} ${currentQuestion.operands[1]} =`
                : "Loading... ="}
            </span>
          </div>

          <input
            id="quick-input"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value.replace(/[^0-9]/g, ""))}
            placeholder="?"
            className="keypad-input"
            autoFocus
          />

          <button type="submit" className="primary keypad-submit" disabled={!inputVal}>
            Submit (Enter) ▶
          </button>
        </form>

        <div className="controls-legend">
          <span>⌨️ <strong>Type your answer & press Enter</strong> or click Submit</span>
        </div>
      </div>
    </div>
  );
};
