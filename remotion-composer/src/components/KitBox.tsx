import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";

// The kit box itself, as the title and end cards' "art" — a live 3D element rather than a
// screenshot, because the film's whole question is what it feels like to be handed one and have it
// open in front of you (docs/video-guidelines.md: a trailer answers one question).
//
// Geometry and colours are client/src/home/KitBox.svelte's, kept deliberately verbatim so the film
// and the home page are the same object: the red lid on a blue border, "30 in ONE" in Alfa Slab
// One over a faint grid, the yellow project badge, and inside it the dark tray holding the board,
// the manual and the coil of wire.
//
// Two things are NOT copied from that component, on purpose:
//
//   1. Its lid animation. `.box.open .lid` rotates `rotateX(-100deg)` about `transform-origin: top
//      center` with nothing on the lid's back, so past 90° the art turns away and the browser draws
//      it through itself. Seth ruled the component's CSS stays untouched and the opening is the
//      compositor's job, so this does it properly instead: the lid has two faces — the printed art
//      and, behind it, the blank kraft underside — each `backface-visibility: hidden`, so at 90°
//      the art edges out of sight and what continues over the top is the inside of a lid, which is
//      what opening a box actually looks like.
//   2. Its CSS `@keyframes` (the LED pulse, the dashed current flow). A CSS animation has no
//      defined value at an arbitrary rendered frame — Remotion renders each frame independently,
//      so those would come out frozen or random. Both are driven off `useCurrentFrame()` here, so
//      the LED breathes and the current crawls deterministically in every render.
export interface KitBoxProps {
  /** 0 = shut, 1 = lid fully back. Drives the hinge; nothing else moves. */
  open: number;
  /** Box width as a fraction of frame width. Height follows the component's own 16/10. */
  widthFrac: number;
  /** Where the box sits, as a fraction of frame width/height (its centre). */
  centerXFrac: number;
  centerYFrac: number;
  displayFont: string;
  headingFont: string;
}

/** Degrees the lid has travelled at `open` = 1: past vertical, so it lies back off the box. */
const LID_OPEN_DEG = 112;
/** The whole box is tilted a little toward the camera, the way one sits on a bench in front of you. */
const BOX_TILT_DEG = 9;

export const KitBox: React.FC<KitBoxProps> = ({
  open, widthFrac, centerXFrac, centerYFrac, displayFont, headingFont,
}) => {
  const frame = useCurrentFrame();
  const { width: frameWidth, height: frameHeight, fps } = useVideoConfig();

  // KitBox.svelte's own 520px-wide, 16/10 box, scaled to the frame: every px below is a
  // `u()` of that component's own number, so the proportions stay its proportions.
  const boxWidth = frameWidth * widthFrac;
  const u = (n: number) => (n * boxWidth) / 520;
  const boxHeight = boxWidth / 1.6;

  const lidDeg = interpolate(open, [0, 1], [0, LID_OPEN_DEG], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // The two frame-driven animations (see the header note). Periods are KitBox.svelte's own:
  // a 1.4s LED pulse, a 0.7s crawl over a 14-unit dash cycle.
  const seconds = frame / fps;
  const ledOpacity = 0.5 + 0.2 * (1 - Math.cos((seconds / 1.4) * 2 * Math.PI)); // 0.5 -> 0.9 -> 0.5
  const flowOffset = -((seconds / 0.7) % 1) * 14;

  const springs: [number, number][] = [[80, 100], [230, 100], [390, 100], [80, 230], [230, 230], [390, 230]];

  return (
    <div
      style={{
        position: "absolute",
        left: frameWidth * centerXFrac - boxWidth / 2,
        top: frameHeight * centerYFrac - boxHeight / 2,
        width: boxWidth,
        height: boxHeight,
        perspective: u(1400),
        perspectiveOrigin: "50% 35%",
      }}
    >
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          transformStyle: "preserve-3d",
          transform: `rotateX(${BOX_TILT_DEG}deg)`,
        }}
      >
        {/* the tray, and what is lying in it */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "#2a1a0c",
            borderRadius: u(8),
            padding: u(14),
            boxSizing: "border-box",
            boxShadow: `inset 0 ${u(10)}px ${u(30)}px rgba(0,0,0,0.6), 0 ${u(20)}px ${u(40)}px rgba(0,0,0,0.5)`,
            display: "grid",
            gridTemplateColumns: `1fr ${u(120)}px`,
            gap: u(10),
          }}
        >
          <svg
            viewBox="0 0 480 300"
            style={{ width: "100%", height: "auto", alignSelf: "center", filter: `drop-shadow(0 ${u(6)}px ${u(10)}px rgba(0,0,0,0.4))` }}
          >
            <rect width="480" height="300" rx="8" fill="#8a5a2b" />
            <rect x="10" y="10" width="460" height="280" rx="6" fill="#e3c891" />
            <text
              x="240" y="40" textAnchor="middle"
              style={{ font: `bold 20px ${displayFont}, 'Arial Black', serif`, fill: "#c0392b", letterSpacing: 2 }}
            >
              OHMSVILLE
            </text>
            {springs.map(([cx, cy]) => (
              <g key={`${cx}-${cy}`}>
                <circle cx={cx} cy={cy} r={10} fill="#d8b23a" stroke="#8a6d1b" strokeWidth={2} />
                <circle cx={cx} cy={cy} r={5} fill="none" stroke="#8a6d1b" />
              </g>
            ))}
            <rect x="120" y="90" width="70" height="20" rx="9" fill="#e6cfa3" stroke="#7a6240" />
            <rect x="136" y="90" width="7" height="20" fill="#f80" />
            <rect x="150" y="90" width="7" height="20" fill="#f80" />
            <rect x="164" y="90" width="7" height="20" fill="#8B4513" />
            <circle cx={310} cy={225} r={26} fill="#ff2a1a" opacity={ledOpacity} style={{ filter: "blur(9px)" }} />
            <path d="M 300 236 L 300 221 A 12 12 0 0 1 322 221 L 322 236 Z" fill="#ff2a1a" stroke="#333" />
            <rect x="296" y="236" width="30" height="5" fill="#444" />
            <path d="M 80 100 Q 80 170 80 230" stroke="#c0392b" strokeWidth={6} fill="none" strokeLinecap="round" />
            <path d="M 230 100 Q 270 180 310 230" stroke="#e6c229" strokeWidth={6} fill="none" strokeLinecap="round" />
            <path
              d="M 230 100 Q 270 180 310 230"
              stroke="#fff" strokeWidth={2} strokeDasharray="3 11" fill="none"
              strokeDashoffset={flowOffset}
            />
            <path d="M 80 230 Q 155 255 230 230" stroke="#2a9d4a" strokeWidth={6} fill="none" strokeLinecap="round" />
          </svg>

          <div
            style={{
              alignSelf: "center",
              background: "#f6eed8",
              color: "#241c10",
              borderRadius: u(3),
              padding: `${u(10)}px ${u(8)}px`,
              transform: "rotate(4deg)",
              boxShadow: `0 ${u(6)}px ${u(12)}px rgba(0,0,0,0.4)`,
              display: "flex",
              flexDirection: "column",
              gap: u(4),
            }}
          >
            <b style={{ font: `600 ${u(12)}px ${headingFont}, 'Trebuchet MS', sans-serif`, letterSpacing: u(1), color: "#a03020" }}>
              LAB MANUAL
            </b>
            <span style={{ font: `${u(10)}px Georgia, serif` }}>every project explained</span>
          </div>

          <div
            style={{
              position: "absolute",
              right: u(24),
              bottom: u(16),
              width: u(70),
              height: u(26),
              borderRadius: "50%",
              background: `repeating-linear-gradient(90deg, #c0392b 0 ${u(4)}px, #e6c229 ${u(4)}px ${u(8)}px, #2a9d4a ${u(8)}px ${u(12)}px, #2b6cd4 ${u(12)}px ${u(16)}px, #222 ${u(16)}px ${u(20)}px)`,
              boxShadow: `0 ${u(4)}px ${u(8)}px rgba(0,0,0,0.5)`,
              transform: "rotate(-12deg)",
            }}
          />
        </div>

        {/* the lid: printed art in front, kraft underside behind, hinged on the box's top edge */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            transformOrigin: "top center",
            transformStyle: "preserve-3d",
            transform: `rotateX(${-lidDeg}deg)`,
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              backfaceVisibility: "hidden",
              background: "#c0392b",
              backgroundImage:
                "linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px)",
              backgroundSize: `${u(26)}px ${u(26)}px`,
              borderRadius: u(8),
              boxShadow: `0 ${u(20)}px ${u(40)}px rgba(0,0,0,0.5)`,
              padding: `${u(22)}px ${u(26)}px`,
              boxSizing: "border-box",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              gap: u(8),
              border: `${u(6)}px solid #1f3a93`,
            }}
          >
            <div style={{ font: `400 ${u(54)}px ${displayFont}, 'Arial Black', serif`, color: "#ffd21f", lineHeight: 1, textShadow: `${u(3)}px ${u(3)}px 0 #1f3a93` }}>
              30 <span style={{ fontSize: u(28) }}>in</span> ONE
            </div>
            <div
              style={{
                display: "inline-block",
                alignSelf: "flex-start",
                background: "#fff",
                color: "#111",
                font: `600 ${u(13)}px ${headingFont}, 'Trebuchet MS', sans-serif`,
                letterSpacing: u(3),
                padding: `${u(3)}px ${u(10)}px`,
              }}
            >
              ELECTRONIC PROJECT KIT
            </div>
            <div
              style={{
                position: "absolute",
                right: u(22),
                top: u(18),
                width: u(74),
                height: u(74),
                borderRadius: "50%",
                background: "#ffd21f",
                color: "#c0392b",
                font: `400 ${u(26)}px ${displayFont}, 'Arial Black', serif`,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                lineHeight: 1,
                border: `${u(3)}px dashed #c0392b`,
                boxSizing: "border-box",
              }}
            >
              30
              <small style={{ font: `600 ${u(9)}px ${headingFont}, 'Trebuchet MS', sans-serif`, letterSpacing: u(1), color: "#1a1408" }}>
                PROJECTS
              </small>
            </div>
          </div>

          {/* the inside of the lid — blank kraft board, which is all there ever is on that face */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              backfaceVisibility: "hidden",
              transform: "rotateY(180deg)",
              background: "#7a4b23",
              backgroundImage: `linear-gradient(160deg, rgba(0,0,0,0.28), rgba(0,0,0,0) 55%)`,
              borderRadius: u(8),
              border: `${u(6)}px solid #5d3718`,
              boxSizing: "border-box",
            }}
          />
        </div>
      </div>
    </div>
  );
};
