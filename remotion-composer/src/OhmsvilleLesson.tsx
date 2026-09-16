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
}

export interface OhmsvilleCut {
  id: string;
  type: "video" | "card" | "title" | "end";
  layer?: number;
  src?: string;
  in_seconds: number;
  out_seconds: number;
  sourceStartSeconds?: number;
  label?: string;
  title?: string;
  subtitle?: string;
  url?: string;
  /** Title/end card only: a background image pushed behind a dark scrim gradient (Home.svelte's
   *  `.spookycard` treatment) — the art recedes, the words sit on the quiet (opaque) side. */
  art?: string;
  /** Title/end card only: a small uppercase line above the headline. */
  kicker?: string;
  /** Video cut only: a corner prop image, large-but-cropped at a frame edge, dimmed toward the
   *  theme's ground — never over a live part or the caption (see CornerProp). */
  prop?: string;
  /** Which top corner `prop` bleeds off of; defaults to "top-right". */
  propCorner?: "top-left" | "top-right";
}

export interface OhmsvilleLessonProps {
  fps?: number;
  width?: number;
  height?: number;
  themeConfig: OhmsvilleTheme;
  cuts: OhmsvilleCut[];
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
  endCard: { url: string; seconds: number; title?: string; kicker?: string; art?: string };
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

/** A title/end card's background art, pushed behind the scrim — absent when `art` is unset, so
 *  every existing lesson card (which never sets it) is unaffected. */
const CardArt: React.FC<{ art?: string; theme: OhmsvilleTheme }> = ({ art, theme }) =>
  art ? (
    <AbsoluteFill>
      <Img src={resolveAsset(art)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      <AbsoluteFill style={{ backgroundImage: scrimGradient(theme.scrimColor || hexToRgb(theme.backgroundColor)) }} />
    </AbsoluteFill>
  ) : null;

/** Corner prop over a board shot (issue #72 fix round 4): large-but-cropped at a frame edge — a
 *  fixed fraction of it hangs off, "a pumpkin half out of frame" rather than a floating sticker —
 *  dimmed and darkened toward the theme's ground rather than sitting bright on top of the live
 *  board. Top corners only: captions dock bottom-center (CaptionOverlay's own paddingBottom), so a
 *  top corner can never cover one, and it stays clear of the board's dense lower rows where the
 *  parts a shot actually cares about tend to sit once focus mode's crop kicks in. */
const CornerProp: React.FC<{ src: string; corner: "top-left" | "top-right"; theme: OhmsvilleTheme }> = ({ src, corner, theme }) => {
  const { height } = useVideoConfig();
  const size = Math.round(height * 0.4);
  const bleed = -Math.round(size * 0.22);
  const side = corner === "top-left" ? { left: bleed } : { right: bleed };
  return (
    <Img
      src={resolveAsset(src)}
      style={{
        position: "absolute",
        top: bleed,
        ...side,
        width: size,
        height: size,
        objectFit: "contain",
        opacity: 0.38,
        // Toward the plum ground, not just faded: darkened and slightly desaturated so it reads as
        // set back rather than a bright sticker laid on top — a plain lower opacity alone still
        // looks bright against Night Shift's own near-black board.
        filter: "brightness(0.55) saturate(0.7)",
        pointerEvents: "none",
      }}
    />
  );
};

const VideoCut: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme }> = ({ cut, theme }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const opacity = useFade(durationInFrames);
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <OffthreadVideo
        src={resolveAsset(cut.src || "")}
        startFrom={Math.round((cut.sourceStartSeconds || 0) * fps)}
        muted
        style={{ width: "100%", height: "100%", objectFit: "cover", opacity }}
      />
      {cut.prop && <CornerProp src={cut.prop} corner={cut.propCorner || "top-right"} theme={theme} />}
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
  const dressed = !!cut.art;
  return (
    <AbsoluteFill
      style={{
        background: theme.backgroundColor,
        border: dressed ? `3px solid ${theme.primaryColor}` : undefined,
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      <CardArt art={cut.art} theme={theme} />
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
  <CardPlate cut={cut} theme={theme} headline={cut.title || ""} headlineSize={cut.art ? 64 : 84} body={cut.subtitle} />
);

const EndPlate: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme; url: string }> = ({ cut, theme, url }) => (
  <CardPlate cut={cut} theme={theme} headline={cut.title || "Keep building at"} headlineSize={cut.art ? 56 : 64} body={url} />
);

// Explicit dispatch — anything not in the four known cut types renders only
// the ground color rather than silently falling through to the end card.
// CardKind on the Ohmsville side includes 'none', so a no-shot/no-card
// section must NOT be mistaken for the lesson's actual end plate.
const CutRenderer: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme; endUrl: string }> = ({ cut, theme, endUrl }) => {
  if (cut.type === "video") return <VideoCut cut={cut} theme={theme} />;
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
        }
      : null;

  return (
    <AbsoluteFill style={{ background: theme.backgroundColor, fontFamily: theme.bodyFont || BODY_FONT }}>
      {cuts.map((cut) => {
        const from = Math.round(cut.in_seconds * fps);
        const duration = Math.max(1, Math.round((cut.out_seconds - cut.in_seconds) * fps));
        return (
          <Sequence key={cut.id} from={from} durationInFrames={duration}>
            <CutRenderer cut={cut} theme={theme} endUrl={endCard?.url || ""} />
          </Sequence>
        );
      })}

      {endCut && endCut.out_seconds > endCut.in_seconds && (
        <Sequence
          from={Math.round(endCut.in_seconds * fps)}
          durationInFrames={Math.max(1, Math.round((endCut.out_seconds - endCut.in_seconds) * fps))}
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
