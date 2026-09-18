import {
  AbsoluteFill,
  CalculateMetadataFunction,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Oswald";
import { loadFont as loadDisplayFont } from "@remotion/google-fonts/AlfaSlabOne";
import { CaptionOverlay, WordCaption } from "./components/CaptionOverlay";
import { KitBox } from "./components/KitBox";

// Ohmsville's "Science Fair '78" identity: deep brown-black ground, warm gold
// rule/accent, oxide-red accent, parchment surface for schematic cards.
const { fontFamily: HEADING_FONT } = loadFont("normal", {
  weights: ["500", "700"],
  subsets: ["latin"],
});
const BODY_FONT = "Georgia, 'Times New Roman', serif";
// The Spooky Shack trailer's own identity (client/src/home/Home.svelte's `.spookycard`, matched
// verbatim — see build_trailer.py's SPOOKY_THEME): a chunky serif headline distinct from every
// other Ohmsville video's Oswald titles. Loaded unconditionally like HEADING_FONT/BODY_FONT — cheap
// even when a theme never sets `displayFont` and so never uses it.
const { fontFamily: DISPLAY_FONT } = loadDisplayFont("normal", { weights: ["400"], subsets: ["latin"] });

export interface OhmsvilleTheme {
  primaryColor: string;
  accentColor: string;
  backgroundColor: string;
  surfaceColor: string;
  textColor: string;
  mutedTextColor: string;
  headingFont: string;
  bodyFont: string;
  captionHighlightColor: string;
  captionBackgroundColor: string;
  /** "r,g,b" for a title/end card's art scrim (see `cut.art`); defaults to the card's own
   *  backgroundColor, converted from hex. */
  scrimColor?: string;
  /** Caption font; falls back to HEADING_FONT when unset, matching every existing lesson. */
  captionFont?: string;
  /** Fix round 7: a small brand mark on every VIDEO cut only (never the title/end cards — the
   *  title already says the name in type, the end card carries the URL). Unset for every existing
   *  lesson, so this is a trailer-only addition with zero effect elsewhere. */
  boardBadge?: string;
  /** Where `boardBadge` sits; defaults to "top-left". */
  boardBadgePosition?: "top-left" | "top-center" | "bottom-left";
}

export interface OhmsvilleCut {
  id: string;
  type: "video" | "card" | "title" | "end" | "image" | "parallax";
  layer?: number;
  src?: string;
  in_seconds: number;
  out_seconds: number;
  sourceStartSeconds?: number;
  label?: string;
  /** "image" cut only (the art model, docs/film-pipeline.md's "Inventor films"): a still
   *  illustration in place of a recorded shot, for a history beat with nothing on the board to
   *  show (Volta's kitchen, the argument, the pile, the shock). One of the five words
   *  videoScript.ts's `art:` line accepts — see imageTransform below for what each one does. */
  motion?: "hold" | "push-in" | "drift-left" | "drift-right" | "pull-out";
  /** "parallax" cut only (#92 draft 4): the beat's planes, BACK TO FRONT. The first is
   *  opaque and the rest carry alpha. See ParallaxCut for what each plane does. */
  layers?: string[];
  /** "parallax" cut only: which way the near planes travel. Defaults to pan-right. */
  parallaxDirection?: "pan-left" | "pan-right";
  title?: string;
  subtitle?: string;
  url?: string;
  /** Title/end card only: a background image pushed behind a dark scrim gradient (Home.svelte's
   *  `.spookycard` treatment) — the art recedes, the words sit on the quiet (opaque) side. */
  art?: string;
  /** Title/end card only: a small uppercase line above the headline. */
  kicker?: string;
  /** Title/end card only, and mutually exclusive with `art`: the kit box itself as the card's
   *  background, live rather than a still. `open: "animate"` hinges the lid back during the cut
   *  (the Box film's first beat); `open: "open"` holds it open (its last). Everything else on the
   *  card — the scrim, the kicker, the headline — is unchanged, so this is one more kind of art,
   *  not a new kind of card. */
  box?: {
    open: "animate" | "open";
    /** seconds into the cut before the lid starts moving; ignored when `open: "open"` */
    openStartSeconds?: number;
    widthFrac?: number;
    centerXFrac?: number;
    centerYFrac?: number;
  };
  /** Video cut only (fix round 8): a corner prop image, over the board's own empty dark corners —
   *  never a manufactured margin. See CornerProp. */
  prop?: string;
  propCorner?: "bottom-left" | "bottom-right";
  /** Target visible height, as a fraction of frame height — chosen per beat by looking at its own
   *  frame (build_trailer.py's PROP_FOR), not a shared default. */
  propHeightFrac?: number;
  /** Opacity, 0-1 — defaults to 0.3; raised per beat where that reads as mush rather than
   *  atmosphere at 20-28% of frame height (Seth: "use your eye"). */
  propOpacity?: number;
  /** CornerProp's darkening filter, 0-1 each — default 0.5/0.65 (see CornerProp). Pale, low-density
   *  art (the ghost: white body, thin dark outline, no saturated fill to hold onto) washes out to
   *  near-nothing against the near-black board at the shared default and needs its own, lighter
   *  treatment; the mummy/pumpkin/zombie-hand art is dense/saturated enough that the shared default
   *  already reads. Per-prop, not a global change — "props should be mostly visible, legible beats
   *  subtle" (video-guidelines.md). */
  propBrightness?: number;
  propSaturate?: number;
}

/** Seth's second, superseding ruling on the inventor films (docs/video-guidelines.md, quoted in
 *  full there): a beat's board or illustration stays on screen, darkened under a scrim, while one
 *  of a FIXED library of animations plays over it — "the electrical current, the resistance, show
 *  the symbols... I want to see examples, not scene after scene of the same board." Kept as a
 *  SEPARATE top-level list, matched 1:1 to build_trailer.py's `overlays` (never folded into
 *  `cuts`), because check_render.py's check_contiguity() requires every cut's `out_seconds` to
 *  equal the next cut's `in_seconds` — an overlay is meant to overlap its own beat's base cut in
 *  time, not sit next to it. `kind` is one of videoScript.ts's six AnimKind values; this file does
 *  not re-validate that (parseAnim already refused anything else before this ever reached a
 *  shotlist), so a new kind needs a matching case in the AnimOverlay dispatch below or it silently
 *  renders nothing. */
export interface OhmsvilleOverlay {
  id: string;
  kind: "current-flow" | "resistance" | "voltage-push" | "symbol-reveal" | "pile-stack" | "lamp-glow";
  in_seconds: number;
  out_seconds: number;
  props?: Record<string, string>;
}

export interface OhmsvilleLessonProps {
  fps?: number;
  width?: number;
  height?: number;
  themeConfig: OhmsvilleTheme;
  cuts: OhmsvilleCut[];
  /** See OhmsvilleOverlay. Optional and defaults to none — every existing lesson (no `anim:` beats)
   *  passes no `overlays` at all, so this is additive with zero effect elsewhere. */
  overlays?: OhmsvilleOverlay[];
  captions: WordCaption[];
  audio: {
    narration?: { src: string; volume?: number };
    music?: {
      src: string;
      volume?: number;
      fade_in_seconds?: number;
      fade_out_seconds?: number;
    };
  };
  endCard: { url: string; seconds: number; title?: string; kicker?: string; art?: string; box?: OhmsvilleCut["box"] };
}

// Same asset-resolution contract as Explainer.tsx / TitledVideo.tsx: URLs and
// data: URIs pass through, absolute paths become file:// URIs, everything
// else — crucially, a public-relative path with NO leading slash — routes
// through staticFile(). A leading "/" here is what makes OffthreadVideo show
// a black frame instead of the staged clip (see build_lesson.py's `src`).
function resolveAsset(src: string): string {
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) {
    return src;
  }
  const clean = src.replace(/^file:\/\/\/?/, "");
  if (clean.startsWith("/") || /^[A-Za-z]:[\\/]/.test(clean)) {
    return `file:///${clean.replace(/\\/g, "/")}`;
  }
  return staticFile(clean);
}

function useFade(durationInFrames: number) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fadeIn = spring({ frame, fps, config: { damping: 20 } });
  const fadeOutStart = durationInFrames - 10;
  const fadeOut = interpolate(frame, [fadeOutStart, durationInFrames], [1, 0.4], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return fadeIn * fadeOut;
}

/** The art model's Ken-Burns motion (see OhmsvilleCut.motion): a still illustration is never
 *  static on screen for a full beat, but the motion is a plain word chosen per beat by what the
 *  picture needs the eye to do, not a formula. `progress` runs 0→1 across the cut's own duration,
 *  so a four-second beat and a seven-second beat both complete exactly one pass of the named
 *  move — never a fixed pixels/frame rate that finishes early or is still crawling at the cut.
 *  Every case scales up beyond 100% first so a pan never reveals the image's own edge. */
function imageTransform(motion: OhmsvilleCut["motion"], progress: number): string {
  const p = Math.max(0, Math.min(1, progress));
  switch (motion) {
    case "push-in":
      return `scale(${1 + 0.12 * p})`;
    case "pull-out":
      return `scale(${1.12 - 0.12 * p})`;
    case "drift-left":
      return `scale(1.14) translateX(${6 - 12 * p}%)`;
    case "drift-right":
      return `scale(1.14) translateX(${-6 + 12 * p}%)`;
    case "hold":
    default:
      // Not literally motionless — a picture held dead still against a moving caption line reads
      // as a slide, not a shot. A slow, barely-there push keeps it feeling like a camera.
      return `scale(${1 + 0.04 * p})`;
  }
}

/** "#140c1c" -> "20,12,28", for building an rgba() scrim from a theme's own hex color. */
function hexToRgb(hex: string): string {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
  if (!m) return "0,0,0";
  return [1, 2, 3].map((i) => parseInt(m[i], 16)).join(",");
}

/** Home.svelte's `.spookycard` gradient, verbatim: opaque (quiet, for the words) on the left,
 *  fading toward the art on the right. */
const scrimGradient = (rgb: string) =>
  `linear-gradient(to right, rgba(${rgb},0.94) 38%, rgba(${rgb},0.55) 62%, rgba(${rgb},0.2))`;

/** The same idea over a `box` card, but clear of the box itself. The gradient above never fully
 *  reaches zero, so it lays roughly a third of a stop over everything to its right — fine for a
 *  photograph that is meant to recede, wrong for the kit box, whose red lid and yellow type are
 *  the one image the film is about. Checked on a real rendered frame: at 0.94/0.55/0.2 the closed
 *  lid came out muddy brown-red with olive lettering. The box's own left edge sits at 45% of frame
 *  width (build_box_film.py's centerXFrac minus half its widthFrac), so this reaches zero there
 *  and the words still sit on solid ground. */
const boxScrimGradient = (rgb: string) =>
  `linear-gradient(to right, rgba(${rgb},0.94) 26%, rgba(${rgb},0.45) 38%, rgba(${rgb},0) 45%)`;

/** The anim overlay's own scrim (see OhmsvilleOverlay/AnimOverlay below) — Seth's own words:
 *  "you can have the table or the board in the background, dark, a dark overlay, and run the
 *  animation." Deliberately FLAT and FULL-FRAME, unlike scrimGradient/boxScrimGradient above:
 *  those are directional and partial because they sit over a title/end card's art, receding on one
 *  side so words have quiet ground on the other. An anim overlay sits over a mid-lesson VIDEO or
 *  IMAGE cut, and Seth's instruction was to dim the *whole* thing evenly, not fade one edge. 65%
 *  is the middle of his "60-70%" range. */
const ANIM_SCRIM = "rgba(0,0,0,0.65)";

/** A `props` value like "9V" or "3" parsed to a plain number, defaulting when absent or
 *  unparseable. Lets one anim kind (current-flow) read a beat-specific number — e.g. Ohm's law
 *  beat plays two current-flow overlays back to back at two different voltages — without adding a
 *  separate mechanism per numeric prop; the label is still shown verbatim so "9V" reads as text
 *  even though only its leading number drives the animation. */
function parseNumericProp(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : fallback;
}

/** Six fixed animations (videoScript.ts's AnimKind) drawn in the same ink/amber schematic style as
 *  the rest of Ohmsville's identity: `theme.accentColor` for the "live" element, `theme.mutedTextColor`
 *  for the inert wire/ground it moves through, `theme.textColor` for the caption line. Each takes
 *  `progress` 0→1 across its OWN overlay duration (see AnimOverlay) so a beat can set any `dur=`
 *  and the animation still completes exactly once — same contract as imageTransform's `progress`
 *  above. None of the six read anything about the base cut underneath; they only know they're
 *  drawn over ANIM_SCRIM. */

const CurrentFlowAnim: React.FC<{ progress: number; theme: OhmsvilleTheme; overlayProps: Record<string, string> }> = ({
  progress,
  theme,
  overlayProps,
}) => {
  // A higher voltage reads as faster-moving charge, not a bigger arrow, so Ohm's "two voltages"
  // beat can play this same kind twice with only `props.voltage` changed.
  const voltage = parseNumericProp(overlayProps.voltage, 1);
  const dashLen = 22;
  const gap = 18;
  const cycle = dashLen + gap;
  const offset = -((progress * cycle * 14 * voltage) % cycle);
  const label = overlayProps.label || (overlayProps.voltage ? `${overlayProps.voltage} · current flow` : "current flow");
  return (
    <svg viewBox="0 0 1000 300" width="62%" style={{ overflow: "visible" }}>
      <line x1="40" y1="150" x2="960" y2="150" stroke={theme.mutedTextColor} strokeWidth={4} opacity={0.35} />
      <line
        x1="40"
        y1="150"
        x2="960"
        y2="150"
        stroke={theme.accentColor}
        strokeWidth={10}
        strokeLinecap="round"
        strokeDasharray={`${dashLen} ${gap}`}
        strokeDashoffset={offset}
      />
      {[0, 1, 2].map((i) => {
        const x = 200 + i * 300;
        return <polygon key={i} points={`${x},118 ${x + 42},150 ${x},182`} fill={theme.accentColor} opacity={0.9} />;
      })}
      <text x="500" y="255" fill={theme.textColor} fontSize={36} fontFamily={theme.headingFont || HEADING_FONT} textAnchor="middle">
        {label}
      </text>
    </svg>
  );
};

const ResistanceAnim: React.FC<{ progress: number; theme: OhmsvilleTheme; overlayProps: Record<string, string> }> = ({
  progress,
  theme,
  overlayProps,
}) => {
  const label = overlayProps.label || "resistance";
  // A breathing glow through the zigzag plus a couple of drifting heat-shimmer strokes above it —
  // "narrower path, current has to work" read as friction/heat rather than a formula on screen.
  const pulse = 0.55 + 0.45 * Math.abs(Math.sin(progress * Math.PI * 3));
  const zigzag = "M60,150 L140,150 L170,90 L230,210 L290,90 L350,210 L410,90 L470,150 L940,150";
  return (
    <svg viewBox="0 0 1000 300" width="62%" style={{ overflow: "visible" }}>
      <path d={zigzag} fill="none" stroke={theme.mutedTextColor} strokeWidth={4} opacity={0.3} />
      <path
        d={zigzag}
        fill="none"
        stroke={theme.accentColor}
        strokeWidth={8}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={pulse}
      />
      {[0, 1, 2].map((i) => (
        <path
          key={i}
          d={`M${170 + i * 120},${70 - 10 * Math.sin(progress * Math.PI * 2 + i)} q15,-20 30,0`}
          fill="none"
          stroke={theme.textColor}
          strokeWidth={2}
          opacity={0.5}
        />
      ))}
      <text x="500" y="260" fill={theme.textColor} fontSize={36} fontFamily={theme.headingFont || HEADING_FONT} textAnchor="middle">
        {label}
      </text>
    </svg>
  );
};

const VoltagePushAnim: React.FC<{ progress: number; theme: OhmsvilleTheme; overlayProps: Record<string, string> }> = ({
  progress,
  theme,
  overlayProps,
}) => {
  const label = overlayProps.label || "voltage — the push";
  const dotCount = 5;
  return (
    <svg viewBox="0 0 1000 300" width="62%" style={{ overflow: "visible" }}>
      {/* battery symbol: long plate (+) then short plate (−), charges pushed away from it */}
      <line x1="480" y1="90" x2="480" y2="210" stroke={theme.accentColor} strokeWidth={8} />
      <line x1="520" y1="120" x2="520" y2="180" stroke={theme.accentColor} strokeWidth={8} />
      <line x1="40" y1="150" x2="480" y2="150" stroke={theme.mutedTextColor} strokeWidth={4} opacity={0.35} />
      <line x1="520" y1="150" x2="960" y2="150" stroke={theme.mutedTextColor} strokeWidth={4} opacity={0.35} />
      {Array.from({ length: dotCount }).map((_, i) => {
        const t = (progress + i / dotCount) % 1;
        // Eased "push": slow leaving the terminal, faster further down the wire.
        const eased = t * t;
        const x = 520 + eased * 420;
        return <circle key={i} cx={x} cy={150} r={12} fill={theme.accentColor} />;
      })}
      <text x="500" y="260" fill={theme.textColor} fontSize={36} fontFamily={theme.headingFont || HEADING_FONT} textAnchor="middle">
        {label}
      </text>
    </svg>
  );
};

/** A small, deliberately non-exhaustive lookup — only the symbols an inventor beat actually names
 *  (`props.symbol`) need to exist here; an unknown or absent one falls back to the resistor zigzag
 *  rather than failing, since a missing schematic symbol is a cosmetic gap, not a broken beat. */
const SYMBOL_PATHS: Record<string, string> = {
  resistor: "M60,150 L140,150 L170,90 L230,210 L290,90 L350,210 L410,90 L470,150 L940,150",
  battery: "M60,150 L460,150 M480,90 L480,210 M520,120 L520,180 M540,150 L940,150",
  led: "M60,150 L440,150 M440,110 L440,190 L520,150 Z M520,110 L520,190 M540,150 L940,150",
};

const SymbolRevealAnim: React.FC<{ progress: number; theme: OhmsvilleTheme; overlayProps: Record<string, string> }> = ({
  progress,
  theme,
  overlayProps,
}) => {
  const symbolKey = (overlayProps.symbol || "resistor").toLowerCase();
  const d = SYMBOL_PATHS[symbolKey] || SYMBOL_PATHS.resistor;
  const rawLabel = overlayProps.label || symbolKey;
  const label = rawLabel.charAt(0).toUpperCase() + rawLabel.slice(1);
  // One generously long dasharray so every symbol above "reveals" as a single continuous stroke
  // regardless of its own path length — offset runs from fully hidden to drawn, finishing slightly
  // before progress=1 so the completed symbol has a beat to sit still before the overlay ends.
  const TOTAL = 2600;
  const offset = TOTAL * (1 - Math.min(1, progress * 1.15));
  return (
    <svg viewBox="0 0 1000 300" width="62%" style={{ overflow: "visible" }}>
      <path d={d} fill="none" stroke={theme.mutedTextColor} strokeWidth={3} opacity={0.25} />
      <path
        d={d}
        fill="none"
        stroke={theme.accentColor}
        strokeWidth={8}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={TOTAL}
        strokeDashoffset={offset}
      />
      <text x="500" y="260" fill={theme.textColor} fontSize={32} fontFamily={theme.headingFont || HEADING_FONT} textAnchor="middle">
        {label}
      </text>
    </svg>
  );
};

// Enough discs to read as "a stack built up disc by disc", not a claim about Volta's actual count.
const PILE_LAYERS = 8;

const PileStackAnim: React.FC<{ progress: number; theme: OhmsvilleTheme; overlayProps: Record<string, string> }> = ({
  progress,
  theme,
  overlayProps,
}) => {
  const label = overlayProps.label || "the pile";
  const shown = Math.min(PILE_LAYERS, Math.floor(progress * (PILE_LAYERS + 1)));
  const discHeight = 22;
  const discWidth = 260;
  const baseY = 250;
  // zinc / silver / brine-soaked cardboard, repeating — Volta's own recipe, not a made-up palette.
  const metals = [theme.accentColor, theme.mutedTextColor, "#7a5230"];
  return (
    <svg viewBox="0 0 1000 300" width="42%" style={{ overflow: "visible" }}>
      {Array.from({ length: PILE_LAYERS }).map((_, i) => {
        const y = baseY - (i + 1) * discHeight;
        return (
          <rect
            key={i}
            x={500 - discWidth / 2}
            y={y}
            width={discWidth}
            height={discHeight - 3}
            rx={4}
            fill={metals[i % metals.length]}
            opacity={i < shown ? 0.95 : 0}
          />
        );
      })}
      <text x="500" y="280" fill={theme.textColor} fontSize={32} fontFamily={theme.headingFont || HEADING_FONT} textAnchor="middle">
        {label}
      </text>
    </svg>
  );
};

const LampGlowAnim: React.FC<{
  progress: number;
  theme: OhmsvilleTheme;
  overlayProps: Record<string, string>;
  gradientId: string;
}> = ({ progress, theme, overlayProps, gradientId }) => {
  const label = overlayProps.label || "lamp glow";
  const glow = progress;
  const haloR = 60 + glow * 140;
  return (
    <svg viewBox="0 0 1000 300" width="46%" style={{ overflow: "visible" }}>
      <defs>
        <radialGradient id={gradientId} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={theme.accentColor} stopOpacity={0.9 * glow} />
          <stop offset="100%" stopColor={theme.accentColor} stopOpacity={0} />
        </radialGradient>
      </defs>
      <circle cx="500" cy="140" r={haloR} fill={`url(#${gradientId})`} />
      <circle cx="500" cy="140" r="50" fill="none" stroke={theme.mutedTextColor} strokeWidth={4} opacity={0.5} />
      <circle cx="500" cy="140" r="50" fill="none" stroke={theme.accentColor} strokeWidth={4} opacity={glow} />
      <line x1="470" y1="120" x2="530" y2="160" stroke={theme.accentColor} strokeWidth={4} opacity={0.4 + 0.6 * glow} />
      <line x1="530" y1="120" x2="470" y2="160" stroke={theme.accentColor} strokeWidth={4} opacity={0.4 + 0.6 * glow} />
      <line x1="500" y1="190" x2="500" y2="230" stroke={theme.mutedTextColor} strokeWidth={6} />
      <text x="500" y="270" fill={theme.textColor} fontSize={32} fontFamily={theme.headingFont || HEADING_FONT} textAnchor="middle">
        {label}
      </text>
    </svg>
  );
};

/** The dispatch videoScript.ts's ANIM_KINDS set exists to keep in sync with: one case per
 *  AnimKind, each returning one of the six components above. An unrecognized `kind` (which
 *  shouldn't reach here — parseAnim already validated it before this ever left build_trailer.py)
 *  falls through to `null`, matching CutRenderer's own unhandled-type behavior rather than
 *  throwing mid-render. */
function renderAnimKind(
  overlay: OhmsvilleOverlay,
  progress: number,
  theme: OhmsvilleTheme,
  overlayProps: Record<string, string>
) {
  switch (overlay.kind) {
    case "current-flow":
      return <CurrentFlowAnim progress={progress} theme={theme} overlayProps={overlayProps} />;
    case "resistance":
      return <ResistanceAnim progress={progress} theme={theme} overlayProps={overlayProps} />;
    case "voltage-push":
      return <VoltagePushAnim progress={progress} theme={theme} overlayProps={overlayProps} />;
    case "symbol-reveal":
      return <SymbolRevealAnim progress={progress} theme={theme} overlayProps={overlayProps} />;
    case "pile-stack":
      return <PileStackAnim progress={progress} theme={theme} overlayProps={overlayProps} />;
    case "lamp-glow":
      return (
        <LampGlowAnim progress={progress} theme={theme} overlayProps={overlayProps} gradientId={`${overlay.id}-halo`} />
      );
    default:
      return null;
  }
}

/** One `anim:` beat, rendered as a full-frame dark scrim (ANIM_SCRIM) plus its animated kind on
 *  top — see OhmsvilleOverlay for why this is a separate Sequence layer from `cuts`, not a field
 *  on one. `durationInFrames` here is this component's OWN Sequence duration (the overlay's
 *  `out_seconds - in_seconds`), the same nested-useVideoConfig contract ImageCut's `progress`
 *  already relies on above — not the composition's total. */
const AnimOverlay: React.FC<{ overlay: OhmsvilleOverlay; theme: OhmsvilleTheme }> = ({ overlay, theme }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const progress = durationInFrames > 1 ? frame / (durationInFrames - 1) : 0;
  const overlayProps = overlay.props || {};
  return (
    <AbsoluteFill style={{ background: ANIM_SCRIM }}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        {renderAnimKind(overlay, progress, theme, overlayProps)}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** The kit box as a card's art (see OhmsvilleCut.box): the lid either hinges back during the cut
 *  or is already lying open. The spring is what a hand does to a cardboard lid — quick, then it
 *  settles — rather than a linear sweep. */
const BoxArt: React.FC<{ box: NonNullable<OhmsvilleCut["box"]>; theme: OhmsvilleTheme }> = ({ box, theme }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const open =
    box.open === "open"
      ? 1
      : spring({
          frame: frame - Math.round((box.openStartSeconds ?? 0) * fps),
          fps,
          config: { damping: 18, stiffness: 70, mass: 1.2 },
        });
  return (
    <AbsoluteFill style={{ background: theme.backgroundColor }}>
      <KitBox
        open={open}
        widthFrac={box.widthFrac ?? 0.46}
        centerXFrac={box.centerXFrac ?? 0.68}
        centerYFrac={box.centerYFrac ?? 0.54}
        displayFont={DISPLAY_FONT}
        headingFont={HEADING_FONT}
      />
    </AbsoluteFill>
  );
};

/** A title/end card's background art, pushed behind the scrim — absent when neither `art` nor
 *  `box` is set, so every existing lesson card (which sets neither) is unaffected. */
const CardArt: React.FC<{ art?: string; box?: OhmsvilleCut["box"]; theme: OhmsvilleTheme }> = ({ art, box, theme }) =>
  art || box ? (
    <AbsoluteFill>
      {box ? (
        <BoxArt box={box} theme={theme} />
      ) : (
        <Img src={resolveAsset(art!)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      )}
      <AbsoluteFill
        style={{
          backgroundImage: (box ? boxScrimGradient : scrimGradient)(theme.scrimColor || hexToRgb(theme.backgroundColor)),
        }}
      />
    </AbsoluteFill>
  ) : null;

// Board cuts carry a corner prop (issue #72, fix rounds 4-8): a top corner sat on the board's
// busiest row (round 4); bottom-anchored fixed that but shrank to invisibility dodging live parts
// at a fixed small size (round 5); scaling the board down to leave a guaranteed-empty margin fixed
// THAT but made the circuit — the subject of the film — a small rectangle with a zombie hand the
// biggest thing on screen (round 6); round 7 removed the props from board beats entirely rather
// than resolve the actual tension. Round 8 (Seth, via the lead: "he never asked for the props to be
// removed; he asked for them to be moved... put them back") is the real fix: the board stays
// full-bleed (round 7's fix, kept). First pass kept the prop clear of every part, in the board's
// own empty dark corners (14-18% of frame height) — Seth's own follow-up dropped that constraint
// entirely: "the props can cover or overlap a little of the board. they should be mostly visible...
// a foreground element, not a watermark hiding in a gap." The WHOLE image now sits in frame (no
// off-frame bleed or crop, natural aspect), 20-28% of frame height, and IS allowed over wires, empty
// board, even a part's edge. What still can't happen: sitting on the caption, or on whichever part
// the narration is naming at that exact moment (build_trailer.py's PROP_FOR, chosen per beat by
// looking at its own frame — see the fix round 8 report).
const CornerProp: React.FC<{
  src: string;
  corner: "bottom-left" | "bottom-right";
  heightFrac: number;
  opacity: number;
  brightness: number;
  saturate: number;
}> = ({ src, corner, heightFrac, opacity, brightness, saturate }) => {
  const { height } = useVideoConfig();
  // Seth, directly, after round 8's first pass: "the props can cover or overlap a little of the
  // board. they should be mostly visible" — not a watermark hiding in a gap, a foreground element.
  // The WHOLE image sits in frame now (no off-frame bleed, no crop), natural aspect via `width:
  // "auto"`, anchored to the bottom corner. Overlapping wires/empty board/a part's edge is fine —
  // what build_trailer.py's PROP_FOR still keeps clear, per beat, is the caption and whichever part
  // the narration is naming at that moment.
  const boxHeight = Math.round(height * heightFrac);
  const side = corner === "bottom-left" ? { left: 20 } : { right: 20 };
  return (
    <Img
      src={resolveAsset(src)}
      style={{
        position: "absolute",
        bottom: 20,
        ...side,
        height: boxHeight,
        width: "auto",
        objectFit: "contain",
        opacity,
        // Darkened toward the board, not just faded — reads as atmosphere sitting in the dark
        // rather than a sticker laid on top of it. Per-prop (build_trailer.py's PROP_FOR): the
        // shared 0.5/0.65 default mushes out pale, low-saturation art like the ghost.
        filter: `brightness(${brightness}) saturate(${saturate})`,
        pointerEvents: "none",
      }}
    />
  );
};

/** A quiet brand mark on a board cut only (fix round 7) — small, roughly 4% of frame height, at a
 *  fixed low opacity so it reads without competing with the board. Never on the title/end cards
 *  (VideoCut is the only caller); "top-left"/"top-center"/"bottom-left" per `theme.boardBadgePosition`
 *  — build_trailer.py's own choice is per-recipe, made by looking at where the board's top row
 *  actually has room, not guessed here. */
const BoardBadge: React.FC<{ src: string; position: "top-left" | "top-center" | "bottom-left"; height: number }> = ({
  src, position, height,
}) => {
  const side: React.CSSProperties =
    position === "bottom-left" ? { left: 24, bottom: 20 }
    : position === "top-center" ? { left: "50%", top: 20, transform: "translateX(-50%)" }
    : { left: 24, top: 20 };
  return (
    <Img
      src={resolveAsset(src)}
      style={{ position: "absolute", ...side, height, width: "auto", opacity: 0.7, pointerEvents: "none" }}
    />
  );
};

const VideoCut: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme }> = ({ cut, theme }) => {
  const { fps, height: frameHeight, durationInFrames } = useVideoConfig();
  const opacity = useFade(durationInFrames);
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <OffthreadVideo
        src={resolveAsset(cut.src || "")}
        startFrom={Math.round((cut.sourceStartSeconds || 0) * fps)}
        muted
        style={{ width: "100%", height: "100%", objectFit: "cover", opacity }}
      />
      {theme.boardBadge && (
        <BoardBadge src={theme.boardBadge} position={theme.boardBadgePosition ?? "top-left"} height={Math.round(frameHeight * 0.04)} />
      )}
      {cut.prop && (
        <CornerProp
          src={cut.prop}
          corner={cut.propCorner || "bottom-right"}
          heightFrac={cut.propHeightFrac ?? 0.24}
          opacity={cut.propOpacity ?? 0.3}
          brightness={cut.propBrightness ?? 0.5}
          saturate={cut.propSaturate ?? 0.65}
        />
      )}
      {cut.label && <LowerThird label={cut.label} theme={theme} />}
    </AbsoluteFill>
  );
};

// The art model's beat: a full-bleed illustration under the captions, in place of a recorded
// shot (build_trailer.py's `elif s.get("art")` branch — a history beat with nothing on the board
// to show). Same full-bleed/no-chrome rule as VideoCut (docs/video-guidelines.md's "the board is
// the subject" — the picture IS the subject here), same fade, same optional label; no corner prop
// (an illustration already carries its own atmosphere) and no board badge (this isn't the board).
const ImageCut: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme }> = ({ cut, theme }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  // useFade's spring starts at literal 0 on this cut's first frame. Everywhere else that's an
  // invisible fade nobody notices, but here the AbsoluteFill it fades in over is filled with
  // theme.backgroundColor — the inventor films' own theme ground, deliberately, so captions and
  // this cut share one color (see INVENTORS_THEME's comment in build_trailer.py: "backgroundColor
  // must not move"). At opacity 0 that reveals a near-solid ground-colored frame at the cut
  // boundary — check_render.py's bare-background scan caught exactly this on real film footage
  // (2 frames, one per image cut, both ~1 RGB unit from ground). A real image's colors sit
  // ~150 units from ground (build_trailer.py's own comment), so a small floor is enough to pull
  // every pixel outside the scan's +/-6 tolerance without the fade reading as a jump cut.
  const opacity = Math.max(useFade(durationInFrames), 0.08);
  const progress = durationInFrames > 1 ? frame / (durationInFrames - 1) : 0;
  return (
    <AbsoluteFill style={{ background: theme.backgroundColor, overflow: "hidden" }}>
      <Img
        src={resolveAsset(cut.src || "")}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity,
          transform: imageTransform(cut.motion, progress),
          transformOrigin: "center center",
        }}
      />
      {cut.label && <LowerThird label={cut.label} theme={theme} />}
    </AbsoluteFill>
  );
};

const CardCut: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme }> = ({ cut, theme }) => {
  const { durationInFrames } = useVideoConfig();
  const opacity = useFade(durationInFrames);
  return (
    <AbsoluteFill
      style={{
        background: theme.surfaceColor,
        opacity,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      {cut.label && (
        <div
          style={{
            position: "absolute",
            top: 48,
            left: 0,
            right: 0,
            textAlign: "center",
            fontFamily: HEADING_FONT,
            fontWeight: 700,
            fontSize: 44,
            letterSpacing: 2,
            textTransform: "uppercase",
            color: theme.primaryColor,
          }}
        >
          {cut.label}
        </div>
      )}
      <Img
        src={resolveAsset(cut.src || "")}
        style={{ maxWidth: "78%", maxHeight: "72%", objectFit: "contain" }}
      />
    </AbsoluteFill>
  );
};

const LowerThird: React.FC<{ label: string; theme: OhmsvilleTheme }> = ({ label, theme }) => (
  <div
    style={{
      position: "absolute",
      bottom: 40,
      left: 48,
      padding: "10px 22px",
      background: theme.captionBackgroundColor,
      borderLeft: `6px solid ${theme.accentColor}`,
      color: theme.textColor,
      fontFamily: HEADING_FONT,
      fontSize: 28,
      textTransform: "uppercase",
      letterSpacing: 1,
    }}
  >
    {label}
  </div>
);

// Shared by TitlePlate/EndPlate: a plain centered plate (every existing lesson card — no `art`) vs.
// Home.svelte's `.spookycard` treatment (`art` set: image behind a scrim, text left-aligned on the
// scrim's opaque/"quiet" side, a kicker line, a border, the headline in DISPLAY_FONT not
// HEADING_FONT). One component, so a lesson's plain card and a trailer's dressed one can never
// silently drift apart into two maintained copies.
const CardPlate: React.FC<{
  cut: OhmsvilleCut;
  theme: OhmsvilleTheme;
  headline: string;
  headlineSize: number;
  body?: string;
}> = ({ cut, theme, headline, headlineSize, body }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 16, stiffness: 90 } });
  const dressed = !!cut.art || !!cut.box;
  return (
    <AbsoluteFill
      style={{
        background: theme.backgroundColor,
        border: dressed ? `3px solid ${theme.primaryColor}` : undefined,
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      <CardArt art={cut.art} box={cut.box} theme={theme} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: dressed ? "flex-start" : "center",
          flexDirection: "column",
          padding: dressed ? "0 9%" : 0,
        }}
      >
        {!dressed && <div style={{ width: 220, height: 6, background: theme.accentColor, marginBottom: 32, transform: `scaleX(${enter})` }} />}
        {cut.kicker && (
          <div
            style={{
              opacity: enter,
              fontFamily: HEADING_FONT,
              fontWeight: 600,
              fontSize: 24,
              letterSpacing: 3,
              textTransform: "uppercase",
              color: theme.accentColor,
              marginBottom: 14,
            }}
          >
            {cut.kicker}
          </div>
        )}
        <div
          style={{
            opacity: enter,
            fontFamily: dressed ? DISPLAY_FONT : HEADING_FONT,
            fontWeight: dressed ? 400 : 700,
            fontSize: headlineSize,
            color: theme.accentColor,
            textAlign: dressed ? "left" : "center",
            maxWidth: dressed ? "70%" : "80%",
          }}
        >
          {headline}
        </div>
        {body && (
          <div style={{ opacity: enter, fontFamily: BODY_FONT, fontSize: dressed ? 30 : 36, color: theme.textColor, marginTop: 20, maxWidth: dressed ? "60%" : undefined }}>
            {body}
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const TitlePlate: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme }> = ({ cut, theme }) => (
  <CardPlate cut={cut} theme={theme} headline={cut.title || ""} headlineSize={cut.art || cut.box ? 64 : 84} body={cut.subtitle} />
);

const EndPlate: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme; url: string }> = ({ cut, theme, url }) => (
  <CardPlate cut={cut} theme={theme} headline={cut.title || "Keep building at"} headlineSize={cut.art || cut.box ? 56 : 64} body={url} />
);


// The parallax model's beat (#92 draft 4). Seth, on draft 3: "shows the same two screens basically
// the whole time, the city that doesn't move." A street built out of separately generated planes —
// sky behind, the shopfront row in the middle, the near kerb in front — each sliding at its own
// rate, which is the one thing a single flat picture of a street cannot do at any Ken-Burns speed.
//
// Everything is driven off useCurrentFrame() rather than a CSS @keyframes animation, for the
// reason docs/film-pipeline.md already records: a keyframe animation has no defined value at an
// arbitrarily rendered frame, so it comes out frozen or wrong in a render that looks right in a
// browser.
//
// `layers` runs BACK TO FRONT. The back plane is opaque and the rest carry alpha, so each one is
// simply painted over the last. Three numbers per plane, all derived from its depth rather than
// authored per beat:
//   rate   how much of the pan it crosses — the back plane barely moves, the front plane crosses
//          all of PARALLAX_PAN_PERCENT. This difference IS the parallax.
//   scale  nearer planes are drawn larger, which is also what keeps a panning plane from ever
//          showing its own edge.
//   drop   nearer planes sit lower in frame, because the camera is standing on the street rather
//          than floating above it. Chosen by compositing the real generated planes and looking at
//          the frame (see the draft-4 notes), not by formula.
const PARALLAX_PAN_PERCENT = 9;
const PARALLAX_PLANES: { scale: number; drop: number; rate: number }[] = [
  { scale: 1.06, drop: 0.0, rate: 0.2 },
  { scale: 1.34, drop: 0.09, rate: 0.6 },
  { scale: 1.45, drop: 0.26, rate: 1.0 },
];
/** A plane's depth numbers. With the usual three layers this is PARALLAX_PLANES as written; with
 *  two or four it spreads them over the same near/far range so a beat is never left with two
 *  planes moving at the same rate, which would read as one picture cut in half. */
function parallaxPlane(index: number, count: number) {
  if (count === PARALLAX_PLANES.length) return PARALLAX_PLANES[index];
  const t = count > 1 ? index / (count - 1) : 0;
  const first = PARALLAX_PLANES[0];
  const last = PARALLAX_PLANES[PARALLAX_PLANES.length - 1];
  return {
    scale: first.scale + (last.scale - first.scale) * t,
    drop: first.drop + (last.drop - first.drop) * t,
    rate: first.rate + (last.rate - first.rate) * t,
  };
}

const ParallaxCut: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme }> = ({ cut, theme }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = useFade(durationInFrames);
  const progress = durationInFrames > 1 ? frame / (durationInFrames - 1) : 0;
  const layers = cut.layers ?? [];
  const sign = cut.parallaxDirection === "pan-left" ? -1 : 1;
  return (
    <AbsoluteFill style={{ background: theme.backgroundColor, overflow: "hidden" }}>
      {layers.map((src, i) => {
        const { scale, drop, rate } = parallaxPlane(i, layers.length);
        // centred on the pan, so the beat opens and closes the same distance either side of the
        // composed frame instead of starting at one edge and crawling off the other
        const x = sign * rate * PARALLAX_PAN_PERCENT * (progress - 0.5);
        return (
          <Img
            key={`${cut.id}-${i}`}
            src={resolveAsset(src)}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              opacity,
              transform: `translateY(${drop * 100}%) scale(${scale}) translateX(${x}%)`,
              transformOrigin: "center center",
            }}
          />
        );
      })}
      {cut.label && <LowerThird label={cut.label} theme={theme} />}
    </AbsoluteFill>
  );
};

// Explicit dispatch — anything not in the four known cut types renders only
// the ground color rather than silently falling through to the end card.
// CardKind on the Ohmsville side includes 'none', so a no-shot/no-card
// section must NOT be mistaken for the lesson's actual end plate.
const CutRenderer: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme; endUrl: string }> = ({ cut, theme, endUrl }) => {
  if (cut.type === "video") return <VideoCut cut={cut} theme={theme} />;
  if (cut.type === "image") return <ImageCut cut={cut} theme={theme} />;
  if (cut.type === "parallax") return <ParallaxCut cut={cut} theme={theme} />;
  if (cut.type === "card") return <CardCut cut={cut} theme={theme} />;
  if (cut.type === "title") return <TitlePlate cut={cut} theme={theme} />;
  if (cut.type === "end") return <EndPlate cut={cut} theme={theme} url={cut.url || endUrl} />;
  return null;
};

export const OhmsvilleLesson: React.FC<OhmsvilleLessonProps> = (props) => {
  const { cuts, captions, audio, endCard, themeConfig: theme } = props;
  const { fps, durationInFrames } = useVideoConfig();

  // A section whose card.kind is "end" (the shotlist's own final section)
  // already comes through as a real "end"-typed cut in `cuts` — build_lesson.py's
  // fallback branch emits `{"type": s["card"]["kind"]}}`, and "end" is one of
  // the four CardKind values (client/src/classroom/videoScript.ts). Only
  // synthesize a second one from the top-level `endCard` field (url + a
  // trailing hold in seconds) when `cuts` doesn't already have one — otherwise
  // the lesson would show the real end plate followed by an identical
  // duplicate reserved by calculateOhmsvilleLessonMetadata's padding.
  const hasEndCut = cuts.some((c) => c.type === "end");
  const lastCutEnd = cuts.length > 0 ? Math.max(...cuts.map((c) => c.out_seconds || 0)) : 0;
  const endCut: OhmsvilleCut | null =
    endCard && !hasEndCut
      ? {
          id: "end-card",
          type: "end",
          in_seconds: lastCutEnd,
          out_seconds: lastCutEnd + (endCard.seconds ?? 0),
          url: endCard.url,
          title: endCard.title,
          kicker: endCard.kicker,
          art: endCard.art,
          box: endCard.box,
        }
      : null;

  return (
    <AbsoluteFill style={{ background: theme.backgroundColor, fontFamily: theme.bodyFont || BODY_FONT }}>
      {cuts.map((cut) => {
        // Both ends are rounded to frames FIRST, and the duration is their difference — never
        // `round((out - in) * fps)`, which is a different number. The compositors hand this
        // component a cut table that is contiguous in seconds (every `out_seconds` is exactly the
        // next `in_seconds`, asserted by build_trailer.py and build_box_film.py), and the identity
        // `round(in·fps) + round((out−in)·fps) === round(out·fps)` does NOT hold in general: it
        // fails whenever the two endpoints round in opposite directions. Measured across all three
        // trailers' shipped cut tables it held at 21 of 23 seams and broke at two — the Spooky
        // Shack's s5→s6 covered one frame twice (harmless, the next Sequence paints over it) and
        // Percepto's s6→s7 left one frame covered by NOTHING, so the theme ground showed through
        // for a frame at 121.73s. That is the same class of bug as the gap this file's siblings
        // bridge in seconds, one order of magnitude down, and it is only visible by scanning
        // frames — the cut table itself is contiguous.
        //
        // Rounding both ends makes each Sequence end exactly where the next begins by
        // construction, at frame granularity. The 21 seams that were already exact are unchanged.
        const from = Math.round(cut.in_seconds * fps);
        const duration = Math.max(1, Math.round(cut.out_seconds * fps) - from);
        return (
          <Sequence key={cut.id} from={from} durationInFrames={duration}>
            <CutRenderer cut={cut} theme={theme} endUrl={endCard?.url || ""} />
          </Sequence>
        );
      })}

      {/* Anim overlays (see OhmsvilleOverlay/AnimOverlay above): a SEPARATE list from `cuts`,
          rendered as additional Sequences positioned here — after the main cuts loop — so each
          one paints on top of its own beat's base cut via DOM order, dimming it under ANIM_SCRIM
          while its animation plays. Each overlay's own `in_seconds`/`out_seconds` are expected to
          fall INSIDE some cut's span (build_trailer.py only emits an overlay under a beat that has
          a `shot:` or `art:` to dim), never required to be contiguous with anything the way `cuts`
          must be for check_render.py's check_contiguity() — that check only ever looks at `cuts`. */}
      {(props.overlays || []).map((overlay) => {
        const from = Math.round(overlay.in_seconds * fps);
        const duration = Math.max(1, Math.round(overlay.out_seconds * fps) - from);
        return (
          <Sequence key={overlay.id} from={from} durationInFrames={duration}>
            <AnimOverlay overlay={overlay} theme={theme} />
          </Sequence>
        );
      })}

      {endCut && endCut.out_seconds > endCut.in_seconds && (
        <Sequence
          from={Math.round(endCut.in_seconds * fps)}
          // Extend to the composition's own `durationInFrames`, not to a second independent
          // round(out_seconds * fps). calculateOhmsvilleLessonMetadata computes the root's total
          // via Math.ceil((lastCutEnd + endSeconds) * fps); this Sequence used to recompute its own
          // end via Math.round on the same seconds value. Those two rounding functions agree only
          // when the fractional frame count is >= 0.5 — inventor-alessandro-volta's tail lands at
          // 2935.2 frames, where ceil gives 2936 but round gives 2935, leaving the render's actual
          // last frame (index 2935) covered by no Sequence at all and showing bare theme ground.
          // Same bug class as the "round both ends" fix above for ordinary cuts (Percepto's
          // s6→s7), one level up: the fix is the same idea, made exact against the frame count the
          // composition actually rendered rather than a second, independently-rounded guess at it.
          durationInFrames={Math.max(1, durationInFrames - Math.round(endCut.in_seconds * fps))}
        >
          <CutRenderer cut={endCut} theme={theme} endUrl={endCard?.url || ""} />
        </Sequence>
      )}

      {captions && captions.length > 0 && (
        <CaptionOverlay
          words={captions}
          wordsPerPage={5}
          fontSize={44}
          // color is left at CaptionOverlay's own default (near-white) unless a theme sets
          // captionFont — every existing lesson theme doesn't, so its captions are unaffected.
          color={theme.captionFont ? theme.textColor : undefined}
          highlightColor={theme.captionHighlightColor}
          backgroundColor={theme.captionBackgroundColor}
          fontFamily={theme.captionFont || HEADING_FONT}
        />
      )}

      {audio?.narration?.src && (
        <Audio src={resolveAsset(audio.narration.src)} volume={audio.narration.volume ?? 1} />
      )}

      {audio?.music?.src && (
        <Audio
          src={resolveAsset(audio.music.src)}
          volume={(f) => {
            const baseVol = audio.music!.volume ?? 0.08;
            const fadeInFrames = (audio.music!.fade_in_seconds ?? 1.5) * fps;
            const fadeOutFrames = (audio.music!.fade_out_seconds ?? 3) * fps;
            const fadeIn = interpolate(f, [0, fadeInFrames], [0, baseVol], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const fadeOut = interpolate(
              f,
              [durationInFrames - fadeOutFrames, durationInFrames],
              [baseVol, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            return Math.min(fadeIn, fadeOut);
          }}
        />
      )}
    </AbsoluteFill>
  );
};

export const calculateOhmsvilleLessonMetadata: CalculateMetadataFunction<
  OhmsvilleLessonProps
> = async ({ props }) => {
  const cuts = props.cuts || [];
  const hasEndCut = cuts.some((c) => c.type === "end");
  const lastCutEnd = cuts.length > 0 ? Math.max(...cuts.map((c) => c.out_seconds || 0)) : 0;
  // Only reserve time for the synthesized end plate when `cuts` doesn't
  // already carry a real "end"-typed cut (the shotlist's own final section) —
  // must match OhmsvilleLesson's own hasEndCut check, or this pads a blank
  // hold onto the tail of a lesson that already ends on its own end plate.
  const endSeconds = hasEndCut ? 0 : props.endCard?.seconds ?? 0;
  const fps = props.fps ?? 30;
  const width = props.width ?? 1920;
  const height = props.height ?? 1080;
  const durationInFrames = Math.max(1, Math.ceil((lastCutEnd + endSeconds) * fps));
  return { durationInFrames, fps, width, height };
};
