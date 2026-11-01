import { cx } from "../lib/cx";

type Props = {
  src: string;
  alt: string;
  caption: string;
  width: number;
  height: number;
  priority?: boolean;
  className?: string;
  imageClassName?: string;
};

export function Figure({
  src,
  alt,
  caption,
  width,
  height,
  priority = false,
  className,
  imageClassName,
}: Props) {
  return (
    <figure className={cx("m-0", className)}>
      <img
        src={src}
        alt={alt}
        width={width}
        height={height}
        loading={priority ? "eager" : "lazy"}
        decoding="async"
        className={cx(
          "h-auto w-full rounded-card border border-line-strong bg-surface",
          imageClassName,
        )}
      />
      <figcaption className="mt-3 max-w-[62ch] text-xs leading-[1.55] text-muted">
        {caption}
      </figcaption>
    </figure>
  );
}
