interface Props {
  className?: string
}

export function Logo({ className }: Props) {
  return (
    <svg
      viewBox="0 0 190 44"
      className={className}
      style={{ overflow: "visible" }}
      aria-label="VENDOS"
      xmlns="http://www.w3.org/2000/svg"
    >
      <text
        x="0"
        y="36"
        fontFamily="'Bebas Neue', sans-serif"
        fontSize="38"
        letterSpacing="5"
        fill="currentColor"
      >
        VENDOS
      </text>
    </svg>
  )
}
