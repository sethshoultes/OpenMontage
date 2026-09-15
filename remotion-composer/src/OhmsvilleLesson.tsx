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
import { CaptionOverlay, WordCaption } from "./components/CaptionOverlay";

// Ohmsville's "Science Fair '78" identity: deep brown-black ground, warm gold
// rule/accent, oxide-red accent, parchment surface for schematic cards.
const { fontFamily: HEADING_FONT } = loadFont("normal", {
  weights: ["500", "700"],
  subsets: ["latin"],
});
const BODY_FONT = "Georgia, 'Times New Roman', serif";

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
}

export interface OhmsvilleLessonProps {
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
  endCard: { url: string; seconds: number };
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

const TitlePlate: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme }> = ({ cut, theme }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 16, stiffness: 90 } });
  return (
    <AbsoluteFill
      style={{
        background: theme.backgroundColor,
        justifyContent: "center",
        alignItems: "center",
        flexDirection: "column",
      }}
    >
      <div style={{ width: 220, height: 6, background: theme.accentColor, marginBottom: 32, transform: `scaleX(${enter})` }} />
      <div
        style={{
          opacity: enter,
          fontFamily: HEADING_FONT,
          fontWeight: 700,
          fontSize: 84,
          color: theme.textColor,
          textAlign: "center",
          maxWidth: "80%",
        }}
      >
        {cut.title}
      </div>
      {cut.subtitle && (
        <div style={{ opacity: enter, fontFamily: BODY_FONT, fontSize: 36, color: theme.mutedTextColor, marginTop: 20 }}>
          {cut.subtitle}
        </div>
      )}
    </AbsoluteFill>
  );
};

const EndPlate: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme; url: string }> = ({ cut, theme, url }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 16, stiffness: 90 } });
  return (
    <AbsoluteFill
      style={{
        background: theme.backgroundColor,
        justifyContent: "center",
        alignItems: "center",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          opacity: enter,
          fontFamily: HEADING_FONT,
          fontWeight: 700,
          fontSize: 64,
          color: theme.accentColor,
          textAlign: "center",
          maxWidth: "80%",
        }}
      >
        {cut.title || "Keep building at"}
      </div>
      <div style={{ opacity: enter, fontFamily: BODY_FONT, fontSize: 40, color: theme.textColor, marginTop: 24 }}>
        {url}
      </div>
      <div style={{ width: 160, height: 4, background: theme.primaryColor, marginTop: 32, transform: `scaleX(${enter})` }} />
    </AbsoluteFill>
  );
};

const CutRenderer: React.FC<{ cut: OhmsvilleCut; theme: OhmsvilleTheme; endUrl: string }> = ({ cut, theme, endUrl }) => {
  if (cut.type === "video") return <VideoCut cut={cut} theme={theme} />;
  if (cut.type === "card") return <CardCut cut={cut} theme={theme} />;
  if (cut.type === "title") return <TitlePlate cut={cut} theme={theme} />;
  return <EndPlate cut={cut} theme={theme} url={cut.url || endUrl} />;
};

export const OhmsvilleLesson: React.FC<OhmsvilleLessonProps> = (props) => {
  const { cuts, captions, audio, endCard, themeConfig: theme } = props;
  const { fps, durationInFrames } = useVideoConfig();

  // build_lesson.py never puts a "end"-typed cut in `cuts` — endCard is a
  // separate top-level field (url + a trailing hold in seconds) that
  // calculateOhmsvilleLessonMetadata already reserves room for. Synthesize
  // the end-plate Sequence here so that reserved time actually shows
  // something, rather than requiring every caller to append its own cut.
  const lastCutEnd = cuts.length > 0 ? Math.max(...cuts.map((c) => c.out_seconds || 0)) : 0;
  const endCut: OhmsvilleCut | null = endCard
    ? {
        id: "end-card",
        type: "end",
        in_seconds: lastCutEnd,
        out_seconds: lastCutEnd + (endCard.seconds ?? 0),
        url: endCard.url,
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
          highlightColor={theme.captionHighlightColor}
          backgroundColor={theme.captionBackgroundColor}
          fontFamily={HEADING_FONT}
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
  const lastCutEnd = cuts.length > 0 ? Math.max(...cuts.map((c) => c.out_seconds || 0)) : 0;
  const endSeconds = props.endCard?.seconds ?? 0;
  const durationInFrames = Math.max(1, Math.ceil((lastCutEnd + endSeconds) * 30));
  return { durationInFrames, fps: 30, width: 1920, height: 1080 };
};
