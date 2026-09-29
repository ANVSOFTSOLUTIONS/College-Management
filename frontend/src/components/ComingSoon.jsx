function ComingSoon({ label }) {
  return (
    <div className="flex h-full min-h-[24rem] flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white text-center">
      <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">Coming soon</p>
      <p className="mt-1 text-lg font-semibold text-slate-700">{label}</p>
      <p className="mt-1 max-w-sm text-sm text-slate-500">This module hasn&apos;t been built yet.</p>
    </div>
  );
}

export default ComingSoon;
