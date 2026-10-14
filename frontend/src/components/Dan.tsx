// Handsome Dan, Yale's bulldog, drawn as simple outline strokes so he reads as a doodle.

export function DanFace({ size = 96, stroke = '#ffffff', strokeWidth = 3, sweater = true }: { size?: number; stroke?: string; strokeWidth?: number; sweater?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" stroke={stroke} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {/* ears */}
      <path d="M26 36 C12 22 16 10 34 22" />
      <path d="M94 36 C108 22 104 10 86 22" />
      {/* big square-ish bulldog head with jowls */}
      <path d="M22 50 C20 24 100 24 98 50 C108 62 104 86 86 94 C72 102 48 102 34 94 C16 86 12 62 22 50 Z" />
      {/* worried brow wrinkles */}
      <path d="M38 42 q6 -5 12 0" />
      <path d="M70 42 q6 -5 12 0" />
      <path d="M54 34 q6 -3 12 0" />
      {/* eyes */}
      <circle cx="44" cy="53" r="3.5" fill={stroke} />
      <circle cx="76" cy="53" r="3.5" fill={stroke} />
      {/* nose + muzzle */}
      <path d="M51 64 q9 -7 18 0 q-9 9 -18 0 Z" fill={stroke} />
      <path d="M60 71 v7" />
      <path d="M60 78 C52 87 40 85 35 76" />
      <path d="M60 78 C68 87 80 85 85 76" />
      {/* underbite teeth */}
      <path d="M48 85 l3 -5 l3 5" />
      <path d="M66 85 l3 -5 l3 5" />
      {/* Y sweater collar */}
      {sweater && (
        <>
          <path d="M34 100 C46 110 74 110 86 100" />
          <path d="M54 104 l6 6 l6 -6 M60 110 v6" />
        </>
      )}
    </svg>
  )
}

function Paw({ x, y, r = 0 }: { x: number; y: number; r?: number }) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${r})`}>
      <ellipse cx="0" cy="6" rx="7" ry="6" />
      <circle cx="-8" cy="-4" r="3" />
      <circle cx="-3" cy="-9" r="3" />
      <circle cx="3" cy="-9" r="3" />
      <circle cx="8" cy="-4" r="3" />
    </g>
  )
}

/** Faint white outline scribbles behind the whole board. */
export function DanDoodles() {
  return (
    <div className="doodles" aria-hidden>
      <div className="doodle d1"><DanFace size={170} strokeWidth={2.2} /></div>
      <div className="doodle d2"><DanFace size={120} strokeWidth={2.4} sweater={false} /></div>
      <div className="doodle d3"><DanFace size={140} strokeWidth={2.2} /></div>
      <svg className="doodle d4" width="260" height="120" viewBox="0 0 260 120" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round">
        <Paw x={30} y={80} r={-20} />
        <Paw x={90} y={50} r={-10} />
        <Paw x={150} y={78} r={-25} />
        <Paw x={210} y={46} r={-12} />
      </svg>
      <svg className="doodle d5" width="140" height="70" viewBox="0 0 140 70" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round">
        {/* a chew bone */}
        <path d="M30 26 C18 10 4 26 16 34 C4 42 18 58 30 42 L110 42 C122 58 136 42 124 34 C136 26 122 10 110 26 Z" />
      </svg>
      <svg className="doodle d6" width="120" height="120" viewBox="0 0 120 120" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round">
        {/* a hand-drawn Yale Y and a squiggle */}
        <path d="M30 20 L60 60 L90 20 M60 60 L60 100" />
        <path d="M20 108 q10 -10 20 0 t20 0 t20 0 t20 0" />
      </svg>
      <svg className="doodle d7" width="90" height="90" viewBox="0 0 90 90" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round">
        <path d="M45 10 l8 22 l23 1 l-18 14 l7 22 l-20 -13 l-20 13 l7 -22 l-18 -14 l23 -1 Z" />
      </svg>
    </div>
  )
}

/** A tiny Handsome Dan 'moji that trots back and forth along the bottom of the page. Click him. */
export function WalkingDan({ onBark }: { onBark?: () => void }) {
  return (
    <div className="walker" aria-hidden onClick={onBark} title="Boola boola!">
      <div className="walker-flip">
        <svg width="64" height="54" viewBox="0 0 64 54">
          {/* body in a navy Yale sweater */}
          <ellipse cx="28" cy="32" rx="20" ry="12" fill="#00356b" stroke="#fff" strokeWidth="2" />
          <text x="22" y="37" fontSize="11" fontWeight="800" fill="#fff" fontFamily="Georgia, serif">Y</text>
          {/* legs (animated) */}
          <g className="legs-a" stroke="#fff" strokeWidth="3" strokeLinecap="round">
            <path d="M14 42 v8" />
            <path d="M38 42 v8" />
          </g>
          <g className="legs-b" stroke="#fff" strokeWidth="3" strokeLinecap="round">
            <path d="M20 42 v8" />
            <path d="M32 42 v8" />
          </g>
          {/* stubby tail */}
          <path d="M8 28 q-5 -4 -2 -8" stroke="#fff" strokeWidth="2.5" fill="none" strokeLinecap="round" />
          {/* head */}
          <circle cx="50" cy="22" r="12" fill="#e9d8c4" stroke="#fff" strokeWidth="2" />
          <path d="M42 12 q-4 -6 2 -6 M56 11 q4 -6 -2 -6" stroke="#fff" strokeWidth="2" fill="#e9d8c4" />
          <circle cx="46" cy="20" r="1.6" fill="#1a1a1a" />
          <circle cx="54" cy="20" r="1.6" fill="#1a1a1a" />
          <ellipse cx="50" cy="25" rx="3" ry="2" fill="#1a1a1a" />
          <path d="M45 29 q5 4 10 0" stroke="#1a1a1a" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        </svg>
      </div>
    </div>
  )
}
