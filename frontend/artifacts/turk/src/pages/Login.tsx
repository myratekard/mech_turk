import { SignIn } from "@clerk/react";
import { Activity } from "lucide-react";

export default function Login() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background p-4 gap-6">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-md bg-primary flex items-center justify-center text-primary-foreground shadow-[0_0_15px_rgba(0,255,255,0.4)]">
          <Activity size={22} strokeWidth={2.5} />
        </div>
        <span className="text-2xl font-black uppercase tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">TURK</span>
      </div>
      <SignIn routing="hash" signUpUrl="/register" forceRedirectUrl="/dashboard" />
    </div>
  );
}
