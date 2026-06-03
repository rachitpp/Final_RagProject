/**
 * Shown before the first streamed token: a breathing ◐ brand glyph beside a
 * rotating caption of the work genuinely happening in the pipeline. It's
 * replaced the instant real text starts streaming.
 */
export default function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2.5 py-1 font-sans text-sm">
      <span className="glyph-breathe font-serif text-lg leading-none text-ink" aria-hidden="true">
        ◐
      </span>
      <span className="thinking-stages">
        <span className="stage stage-1">Embedding query</span>
        <span className="stage stage-2">Retrieving passages</span>
        <span className="stage stage-3">Reading sources</span>
      </span>
    </div>
  );
}
