// The analysis is a wizard: each step must be finished before the next one
// makes sense (you can't run statistics before you know the column types).

export const STEPS = ["Upload", "Columns", "Privacy", "Cleaning", "Dashboard"] as const;

export function StepIndicator({ current }: { current: number }) {
  return (
    <ol className="steps" aria-label="Progress">
      {STEPS.map((label, i) => {
        const state = i < current ? "done" : i === current ? "current" : "todo";
        return (
          <li key={label} className={`step step-${state}`} aria-current={i === current ? "step" : undefined}>
            <span className="step-number">{i + 1}</span>
            <span className="step-label">{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
