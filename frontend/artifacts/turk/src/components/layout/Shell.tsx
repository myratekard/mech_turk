import { ReactNode, useState, useEffect } from "react";
import { Link, useLocation } from "wouter";
import { Activity, UploadCloud, LayoutDashboard, BookOpen, ShieldCheck, Building2, Users as UsersIcon, GitBranch, LogOut, BarChart3, Menu, Receipt } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

interface ShellProps {
  children: ReactNode;
}

export function Shell({ children }: ShellProps) {
  const [location] = useLocation();
  const { user, logout, isAdmin, isSuperuser, isOrgAdmin, canReview } = useAuth();
  const [navOpen, setNavOpen] = useState(false);
  const [reviewCount, setReviewCount] = useState(0);

  // Reviewers (superuser/turk_admin) get a live count of pending submissions on the Review nav.
  useEffect(() => {
    if (!canReview) return;
    let alive = true;
    const tick = () => api.reviewCount().then((r) => alive && setReviewCount(r.count)).catch(() => {});
    tick();
    const id = setInterval(tick, 20000);
    return () => { alive = false; clearInterval(id); };
  }, [canReview]);

  const initials = (user?.username || "user").slice(0, 2).toUpperCase();
  const avatar = `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><rect width='64' height='64' fill='#15151e'/><text x='32' y='42' font-size='24' text-anchor='middle' fill='#00e5ff' font-family='sans-serif'>${initials}</text></svg>`,
  )}`;

  // Nav is role-aware: base items for everyone, admin items gated.
  const navItems: { href: string; icon: any; label: string; badge?: number }[] = [
    { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
    { href: "/upload", icon: UploadCloud, label: "Upload" },
    { href: "/submissions", icon: Activity, label: "Submissions" },
    ...(isOrgAdmin ? [{ href: "/referrals", icon: GitBranch, label: "Referrals" }] : []),
    ...(canReview ? [{ href: "/admin/review", icon: ShieldCheck, label: "Review", badge: reviewCount }] : []),
    ...(isAdmin ? [{ href: "/admin/analytics", icon: BarChart3, label: "Analytics" }] : []),
    ...((isOrgAdmin || isSuperuser) ? [{ href: "/admin/invoices", icon: Receipt, label: "Invoices" }] : []),
    ...(isOrgAdmin ? [{ href: "/admin/staff", icon: UsersIcon, label: "Staff" }] : []),
    ...(isSuperuser ? [{ href: "/admin/orgs", icon: Building2, label: "Organizations" }] : []),
    ...(isSuperuser ? [{ href: "/admin/turk-admins", icon: ShieldCheck, label: "Turk Admins" }] : []),
    ...(isSuperuser ? [{ href: "/admin/users", icon: UsersIcon, label: "Users" }] : []),
    { href: "/instructions", icon: BookOpen, label: "Instructions" },
  ];

  // Sidebar contents are shared by the desktop aside and the mobile drawer.
  const SidebarBody = ({ onNavigate }: { onNavigate?: () => void }) => (
    <div className="flex flex-col h-full">
      <div className="p-6 flex items-center gap-3 border-b border-border">
        <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center text-primary-foreground shadow-[0_0_15px_rgba(0,255,255,0.4)]">
          <Activity size={20} strokeWidth={2.5} />
        </div>
        <span className="text-xl font-bold tracking-widest uppercase text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">TURK</span>
      </div>

      <nav className="flex-1 py-6 px-4 space-y-2 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = location === item.href || (item.href !== "/" && location.startsWith(item.href));
          return (
            <Link key={item.href} href={item.href} data-testid={`nav-${item.label.toLowerCase()}`} onClick={onNavigate}>
              <span
                className={cn(
                  "flex items-center gap-3 px-4 py-3 rounded-md transition-all duration-200 group cursor-pointer font-medium text-sm",
                  isActive
                    ? "bg-primary/10 text-primary border border-primary/20 shadow-[inset_0_0_20px_rgba(0,255,255,0.05)]"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                )}
              >
                <item.icon
                  size={18}
                  className={cn("transition-colors", isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground")}
                />
                {item.label}
                {item.badge ? (
                  <span className="ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-primary text-primary-foreground text-[10px] font-black shadow-[0_0_10px_rgba(0,255,255,0.4)]">
                    {item.badge}
                  </span>
                ) : null}
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border mt-auto">
        <div className="flex items-center gap-3 px-2 py-3 mb-2">
          <div className="w-8 h-8 rounded-full bg-muted overflow-hidden border border-border">
            <img src={avatar} alt={user?.username || "user"} className="w-full h-full object-cover" />
          </div>
          <div className="flex flex-col flex-1 overflow-hidden">
            <span className="text-sm font-semibold truncate">{user?.username || "—"}</span>
            <span className="text-xs text-muted-foreground truncate font-mono uppercase">{user?.role}</span>
          </div>
        </div>
        <Button
          variant="outline"
          className="w-full justify-start gap-2 border-border/50 hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30"
          onClick={() => { onNavigate?.(); logout(); }}
          data-testid="button-logout"
        >
          <LogOut size={16} />
          Sign Out
        </Button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex flex-col md:flex-row w-full bg-background text-foreground selection:bg-primary/30">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-64 border-r border-border bg-card/50 backdrop-blur-xl flex-col sticky top-0 h-screen z-40">
        <SidebarBody />
      </aside>

      {/* Mobile top bar + slide-out nav drawer */}
      <header className="md:hidden sticky top-0 z-40 flex items-center justify-between px-4 h-14 border-b border-border bg-card/80 backdrop-blur-xl">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-primary flex items-center justify-center text-primary-foreground shadow-[0_0_15px_rgba(0,255,255,0.4)]">
            <Activity size={16} strokeWidth={2.5} />
          </div>
          <span className="text-lg font-bold tracking-widest uppercase text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">TURK</span>
        </div>
        <Sheet open={navOpen} onOpenChange={setNavOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Open navigation" data-testid="button-nav-menu" className="relative">
              <Menu size={22} />
              {canReview && reviewCount > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-primary shadow-[0_0_8px_rgba(0,255,255,0.6)]" />
              )}
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-72 bg-card border-border">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <SidebarBody onNavigate={() => setNavOpen(false)} />
          </SheetContent>
        </Sheet>
      </header>

      <main className="flex-1 flex flex-col min-w-0">{children}</main>
    </div>
  );
}
