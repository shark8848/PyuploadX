export function ProgressBar({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  return (
    <div className="progress">
      <div className="progress-fill" style={{ width: `${percent}%` }} />
      <span className="progress-label">{percent}%</span>
    </div>
  );
}
