// Brand mark: a speech bubble (a survey answer) containing rising bars (insight).
export function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true" className="logo">
      <rect x="2" y="2" width="36" height="30" rx="9" fill="var(--accent)" />
      <path d="M11 32 L11 38 L18 32 Z" fill="var(--accent)" />
      <rect x="10" y="18" width="4.5" height="8" rx="1.5" fill="var(--on-accent)" opacity="0.7" />
      <rect x="17.75" y="13" width="4.5" height="13" rx="1.5" fill="var(--on-accent)" opacity="0.85" />
      <rect x="25.5" y="8" width="4.5" height="18" rx="1.5" fill="var(--on-accent)" />
    </svg>
  );
}
