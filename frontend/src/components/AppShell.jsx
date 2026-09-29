import DeveloperCredit from "./DeveloperCredit";
import InstallBanner from "./InstallBanner";
import NotificationBell from "./NotificationBell";

const CONSOLE_TITLES = { admin: "Admin console", teacher: "Faculty console", parent: "Parent portal", student: "Student portal" };

function AppShell({ navItems, activeNav, onNavChange, user, onLogout, apiStatus, children }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-4 sm:px-6">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">College management platform</p>
          <h1 className="text-lg font-bold text-slate-900">{CONSOLE_TITLES[user.role] ?? "Console"}</h1>
        </div>
        <div className="flex items-center gap-4">
          <span
            className={`hidden items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold sm:inline-flex ${
              apiStatus === "online"
                ? "bg-emerald-50 text-emerald-700"
                : apiStatus === "offline"
                  ? "bg-rose-50 text-rose-700"
                  : "bg-amber-50 text-amber-700"
            }`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
            Backend {apiStatus}
          </span>
          <div className="flex items-center gap-3 text-sm">
            <InstallBanner compact />
            <NotificationBell onOpenLink={(link) => navItems.some((item) => item.id === link) && onNavChange(link)} />
            <div className="hidden text-right leading-tight sm:block">
              <p className="font-semibold text-slate-800">{user.full_name}</p>
              <p className="text-xs capitalize text-slate-400">{user.role === "teacher" ? "faculty" : user.role}</p>
            </div>
            <button
              type="button"
              onClick={onLogout}
              className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      {/* Phones: the side menu becomes a scrollable strip under the header. */}
      <nav aria-label="Sections" className="overflow-x-auto border-b border-slate-200 bg-white px-2 md:hidden">
        <ul className="flex gap-1 py-2">
          {navItems.map((item) => (
            <li key={item.id} className="shrink-0">
              <button
                type="button"
                onClick={() => onNavChange(item.id)}
                className={`rounded-full px-3 py-1.5 text-sm font-medium ${
                  activeNav === item.id ? "bg-emerald-600 text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="mx-auto flex max-w-7xl">
        <nav className="hidden w-56 shrink-0 border-r border-slate-200 bg-white p-4 md:block">
          <ul className="space-y-1">
            {navItems.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => onNavChange(item.id)}
                  className={`w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors ${
                    activeNav === item.id
                      ? "bg-emerald-50 text-emerald-800"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <main className="flex min-w-0 flex-1 flex-col p-4 sm:p-6">
          <div className="flex-1">{children}</div>
          <DeveloperCredit className="mt-10 pb-2" />
        </main>
      </div>
    </div>
  );
}

export default AppShell;
