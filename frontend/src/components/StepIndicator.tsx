// The analysis is a wizard: each step must be finished before the next one
// makes sense (you can't run statistics before you know the column types).

export const STEPS = ["Upload", "Columns", "Privacy", "Cleaning", "Dashboard"] as const;

export function StepIndicator({ current }: { current: number }) {
  return (
    <ol className="steps" aria-label="Progress">
      {STEPS.map((label, i) => {
        const state = i < current ? "done" : i === current ? "current" : "todo";
        return (
          <li
            key={label}
            className={`step step-${state}`}
            aria-current={i === current ? "step" : undefined}
          >
            <span className="step-number">
              {state === "done" ? (
                <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                  <path
                    d="M2.5 6.5 5 9l4.5-6"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                i + 1
              )}
            </span>
            <span className="step-label">{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
