import { ReactNode } from "react";
import { Link, useLocation } from "wouter";
import { Activity, UploadCloud, LayoutDashboard, BookOpen, ShieldCheck, Building2, Users as UsersIcon, GitBranch, LogOut, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

interface ShellProps {
  children: ReactNode;
}

export function Shell({ children }: ShellProps) {
  const [location] = useLocation();
  const { user, logout, isAdmin, isSuperuser, isOrgAdmin, canReview } = useAuth();

  const initials = (user?.username || "user").slice(0, 2).toUpperCase();
  const avatar = `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><rect width='64' height='64' fill='#15151e'/><text x='32' y='42' font-size='24' text-anchor='middle' fill='#00e5ff' font-family='sans-serif'>${initials}</text></svg>`,
  )}`;

  // Nav is role-aware: base items for everyone, admin items gated.
  const navItems: { href: string; icon: any; label: string }[] = [
    { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
    { href: "/upload", icon: UploadCloud, label: "Upload" },
    { href: "/submissions", icon: Activity, label: "Submissions" },
    ...(isOrgAdmin ? [{ href: "/referrals", icon: GitBranch, label: "Referrals" }] : []),
    ...(canReview ? [{ href: "/admin/review", icon: ShieldCheck, label: "Review" }] : []),
    ...(isAdmin ? [{ href: "/admin/analytics", icon: BarChart3, label: "Analytics" }] : []),
    ...(isOrgAdmin ? [{ href: "/admin/staff", icon: UsersIcon, label: "Staff" }] : []),
    ...(isSuperuser ? [{ href: "/admin/orgs", icon: Building2, label: "Organizations" }] : []),
    ...(isSuperuser ? [{ href: "/admin/turk-admins", icon: ShieldCheck, label: "Turk Admins" }] : []),
    ...(isSuperuser ? [{ href: "/admin/users", icon: UsersIcon, label: "Users" }] : []),
    { href: "/instructions", icon: BookOpen, label: "Instructions" },
  ];

  return (
    <div className="min-h-screen flex flex-col md:flex-row w-full bg-background text-foreground selection:bg-primary/30">
      <aside className="w-full md:w-64 border-b md:border-b-0 md:border-r border-border bg-card/50 backdrop-blur-xl flex flex-col sticky top-0 md:h-screen z-40">
        <div className="p-6 flex items-center gap-3 border-b border-border">
          <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center text-primary-foreground shadow-[0_0_15px_rgba(0,255,255,0.4)]">
            <Activity size={20} strokeWidth={2.5} />
          </div>
          <span className="text-xl font-bold tracking-tight uppercase tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">TURK</span>
        </div>

        <nav className="flex-1 py-6 px-4 space-y-2 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = location === item.href || (item.href !== "/" && location.startsWith(item.href));
            return (
              <Link key={item.href} href={item.href} data-testid={`nav-${item.label.toLowerCase()}`}>
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
            onClick={logout}
            data-testid="button-logout"
          >
            <LogOut size={16} />
            Sign Out
          </Button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0">{children}</main>
    </div>
  );
}
