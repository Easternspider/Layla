"use client";

/** Спокойный фоновый свет: два больших размытых градиента, медленный дрейф. */
export function AuroraBackdrop() {
  return (
    <div className="aurora-backdrop" aria-hidden="true">
      <div className="aurora-wash aurora-a" />
      <div className="aurora-wash aurora-b" />
    </div>
  );
}
