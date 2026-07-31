// MyMemory logo — constellation mark on a soft teal tile (Lumen).

export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      role="img"
      aria-label="MyMemory"
    >
      <defs>
        <linearGradient
          id="mm-tile"
          x1="4"
          y1="2"
          x2="44"
          y2="46"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#5eb8ad" />
          <stop offset="1" stopColor="#0f8f86" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="44" height="44" rx="14" fill="url(#mm-tile)" />
      <g stroke="#f3f7fb" strokeWidth="2.2" strokeLinecap="round" opacity="0.95">
        <line x1="24" y1="26" x2="14" y2="15" />
        <line x1="24" y1="26" x2="34" y2="16" />
        <line x1="24" y1="26" x2="34" y2="35" />
        <line x1="24" y1="26" x2="15" y2="35" />
      </g>
      <g fill="#f3f7fb">
        <circle cx="24" cy="26" r="4.2" />
        <circle cx="14" cy="15" r="2.6" />
        <circle cx="34" cy="16" r="2.6" />
        <circle cx="34" cy="35" r="2.6" />
        <circle cx="15" cy="35" r="2.6" />
      </g>
    </svg>
  );
}

export function Logo({
  iconSize = 26,
  hero = false,
}: {
  iconSize?: number;
  hero?: boolean;
}) {
  return (
    <span className={hero ? "logo logo-hero" : "logo"}>
      <LogoMark size={iconSize} />
      <span className="logo-word">MYMEMORY</span>
    </span>
  );
}
