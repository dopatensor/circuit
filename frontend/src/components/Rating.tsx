/** Five buttons, 1 to 5. Used for intros and circuits. */
export function Rating({
  question,
  disabled,
  onRate,
}: {
  question: string;
  disabled?: boolean;
  onRate: (rating: number) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-sm">{question}</legend>
      <div className="flex gap-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            disabled={disabled}
            aria-label={`${n} of 5`}
            onClick={() => onRate(n)}
            className="min-h-11 min-w-11 flex-1 cursor-pointer rounded-xl border border-line bg-raised font-semibold tabular-nums hover:border-fg2 disabled:opacity-40"
          >
            {n}
          </button>
        ))}
      </div>
      <p className="flex justify-between text-sm text-muted">
        <span>Not useful</span>
        <span>Very useful</span>
      </p>
    </fieldset>
  );
}
