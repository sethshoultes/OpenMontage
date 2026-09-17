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
          box: endCard.box,
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
