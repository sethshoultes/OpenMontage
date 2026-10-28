import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface TextCardProps {
  text: string;
  fontSize?: number;
  color?: string;
  backgroundColor?: string;
  /** Fade the text out over this many seconds at the end of the card, so a title never snaps off. */
  fadeOutSeconds?: number;
  /** Put the text this fraction of the frame height from the top instead of centred. */
  topOffset?: number;
  /** Left-align the text at this fraction of the frame width from the left (with topOffset it sets a column). */
  leftOffset?: number;
}

export const TextCard: React.FC<TextCardProps> = ({
  text,
  fontSize = 64,
  color = "#FFFFFF",
  backgroundColor = "#1F2937",
  fadeOutSeconds,
  topOffset,
  leftOffset,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, height, width } = useVideoConfig();

  const fadeIn = spring({ frame, fps, config: { damping: 20 } });
  const fadeOut = fadeOutSeconds
    ? Math.min(1, Math.max(0, (durationInFrames - frame) / (fadeOutSeconds * fps)))
    : 1;
  const opacity = fadeIn * fadeOut;
  const scale = spring({
    frame,
    fps,
    config: { damping: 15, stiffness: 100 },
    from: 0.95,
    to: 1,
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: topOffset === undefined ? "center" : "flex-start",
        alignItems: leftOffset === undefined ? "center" : "flex-start",
        paddingTop: topOffset === undefined ? 0 : height * topOffset,
        paddingLeft: leftOffset === undefined ? 0 : width * leftOffset,
        background: backgroundColor,
      }}
    >
      <div
        style={{
          opacity,
          transform: `scale(${scale})`,
          fontSize,
          color,
          fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 700,
          textAlign: leftOffset === undefined ? "center" : "left",
          maxWidth: leftOffset === undefined ? "80%" : "36%",
          lineHeight: 1.3,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
