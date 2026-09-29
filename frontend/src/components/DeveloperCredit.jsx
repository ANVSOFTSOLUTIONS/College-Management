// "Developed by ANV Soft Solutions Pvt Ltd" with the secure badge, shown on the login page and inside the app.
function DeveloperCredit({ className = "" }) {
  return (
    <p className={`flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs text-slate-500 ${className}`}>
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-800">
        <svg aria-hidden="true" viewBox="0 0 20 20" className="h-3 w-3 fill-current">
          <path d="M10 1a4.5 4.5 0 0 0-4.5 4.5V8H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2h-.5V5.5A4.5 4.5 0 0 0 10 1Zm2.5 7h-5V5.5a2.5 2.5 0 0 1 5 0V8Z" />
        </svg>
        Secure software
      </span>
      <span>
        Developed by <span className="font-semibold text-slate-700">ANV Soft Solutions Pvt Ltd</span>
      </span>
    </p>
  );
}

export default DeveloperCredit;
