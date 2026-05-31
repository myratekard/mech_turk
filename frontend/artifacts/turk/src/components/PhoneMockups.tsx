import * as React from "react";

/* Verified badge matching real platform style — solid blue circle, white checkmark */
function Verified({ size = 10 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" className="inline-block flex-shrink-0" aria-label="Verified">
      <circle cx="10" cy="10" r="10" fill="#1D9BF0" />
      <path d="M6 10.5l2.5 2.5 5.5-5.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ─── Instagram (dark mode) ───────────────────────────── */
export function InstagramScreen() {
  const grid = [
    "from-rose-400 to-pink-600",
    "from-amber-400 to-orange-500",
    "from-sky-400 to-blue-600",
    "from-violet-400 to-purple-600",
    "from-emerald-400 to-teal-600",
    "from-fuchsia-400 to-rose-500",
    "from-cyan-400 to-sky-500",
    "from-orange-400 to-red-500",
    "from-green-400 to-emerald-600",
  ];
  const highlights = [
    { label: "Travel", g: "from-yellow-400 to-orange-500" },
    { label: "Style", g: "from-pink-400 to-rose-600" },
    { label: "Food", g: "from-green-400 to-teal-500" },
    { label: "Life", g: "from-blue-400 to-indigo-600" },
  ];

  return (
    <div className="bg-black text-white select-none" style={{ fontSize: 7 }}>
      {/* Status bar */}
      <div className="flex justify-between items-center px-3 pt-2 pb-0.5 text-white" style={{ fontSize: 8, fontWeight: 600 }}>
        <span>9:41</span>
        <div className="flex items-center gap-1">
          <svg width="12" height="8" viewBox="0 0 15 11" fill="white"><rect x="0" y="4" width="3" height="7" rx="0.5"/><rect x="4" y="2.5" width="3" height="8.5" rx="0.5"/><rect x="8" y="1" width="3" height="10" rx="0.5"/><rect x="12" y="0" width="3" height="11" rx="0.5" opacity="0.3"/></svg>
          <svg width="12" height="8" viewBox="0 0 24 18" fill="white"><path d="M12 3C7.5 3 3.5 4.9.5 8L2 9.5C4.6 7 8.1 5.5 12 5.5s7.4 1.5 10 4L23.5 8C20.5 4.9 16.5 3 12 3z"/><path d="M12 8c-3 0-5.7 1.2-7.7 3.1L5.8 12.6C7.4 11 9.6 10 12 10s4.6 1 6.2 2.6l1.5-1.5C17.7 9.2 15 8 12 8z"/><circle cx="12" cy="16" r="2"/></svg>
          <div className="flex items-center gap-0.5">
            <div className="w-4 h-2 border border-white rounded-sm relative"><div className="absolute inset-0.5 right-1 bg-white rounded-sm" /><div className="absolute right-0 top-0.5 w-0.5 h-1 bg-white rounded-r-sm" /></div>
          </div>
        </div>
      </div>

      {/* Top nav */}
      <div className="flex items-center justify-between px-3 py-1.5">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
        <div className="flex items-center gap-1">
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: -0.2 }}>viralcreator</span>
          <Verified size={11} />
        </div>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="white"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>
      </div>

      {/* Profile info */}
      <div className="px-3 pb-2">
        <div className="flex items-center gap-2.5 mb-2">
          {/* Avatar with gradient ring */}
          <div className="rounded-full p-[1.5px] flex-shrink-0" style={{ background: "linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888)" }}>
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-violet-500 to-pink-500 border-[1.5px] border-black" />
          </div>
          {/* Stats */}
          <div className="flex flex-1 justify-around">
            {[["601","posts"],["271K","followers"],["344","following"]].map(([n,l])=>(
              <div key={l} className="flex flex-col items-center">
                <span style={{ fontSize: 10, fontWeight: 800 }}>{n}</span>
                <span style={{ fontSize: 7, color: "#aaa" }}>{l}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ fontSize: 9, fontWeight: 700, marginBottom: 1 }}>Viral Creator Studio</div>
        <div style={{ fontSize: 7, color: "#ccc", lineHeight: 1.4 }}>🎬 Content · 📲 Social Media</div>
        <div style={{ fontSize: 7, color: "#1d9bf0", marginBottom: 4 }}>🔗 linktr.ee/viralcreator</div>

        {/* Action buttons */}
        <div className="flex gap-1.5 mb-2.5">
          <button className="flex-1 rounded-md py-1 text-white font-bold" style={{ fontSize: 8, background: "#0095f6" }}>Follow</button>
          <button className="flex-1 rounded-md py-1 font-bold" style={{ fontSize: 8, background: "#262626", color: "#fff" }}>Message</button>
          <button className="rounded-md px-2 py-1 font-bold" style={{ fontSize: 8, background: "#262626", color: "#fff" }}>▾</button>
        </div>

        {/* Story highlights */}
        <div className="flex gap-2 overflow-hidden">
          {highlights.map(h=>(
            <div key={h.label} className="flex flex-col items-center gap-0.5 flex-shrink-0">
              <div className={`w-9 h-9 rounded-full bg-gradient-to-br ${h.g} border-2 border-black`} style={{ boxShadow: "0 0 0 1.5px #555" }} />
              <span style={{ fontSize: 6, color: "#ccc" }}>{h.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Grid / Reels tabs */}
      <div className="flex border-t border-neutral-800">
        <div className="flex-1 flex justify-center py-1.5 border-b border-white">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="white"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
        </div>
        <div className="flex-1 flex justify-center py-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#777" strokeWidth="1.5"><path d="M15 10l4.553-2.276A1 1 0 0121 8.72v6.56a1 1 0 01-1.447.894L15 14v-4z"/><rect x="3" y="6" width="12" height="12" rx="2"/></svg>
        </div>
      </div>

      {/* Photo grid */}
      <div className="grid grid-cols-3 gap-[1px] bg-neutral-800">
        {grid.map((g,i)=>(
          <div key={i} className={`aspect-square bg-gradient-to-br ${g}`} />
        ))}
      </div>

      {/* Bottom nav */}
      <div className="flex justify-around items-center px-2 py-2 border-t border-neutral-800">
        {[
          <path key="h" d="M3 12l9-9 9 9M5 10v9h4v-6h6v6h4v-9" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round"/>,
          <><circle key="s1" cx="11" cy="11" r="8" stroke="#888" strokeWidth="1.5" fill="none"/><path key="s2" d="M21 21l-4-4" stroke="#888" strokeWidth="1.5" strokeLinecap="round"/></>,
          <rect key="+" x="4" y="4" width="16" height="16" rx="3" stroke="#888" strokeWidth="1.5" fill="none"/>,
          <path key="r" d="M15 10l4.553-2.276A1 1 0 0121 8.72v6.56a1 1 0 01-1.447.894L15 14v-4zM3 8.72a1 1 0 011.447-.894L9 10v4l-4.553 2.276A1 1 0 013 15.28V8.72z" stroke="#888" strokeWidth="1.5" fill="none"/>,
          <><circle key="p" cx="12" cy="8" r="4" stroke="#888" strokeWidth="1.5" fill="none"/><path key="p2" d="M4 20a8 8 0 0116 0" stroke="#888" strokeWidth="1.5" fill="none" strokeLinecap="round"/></>,
        ].map((icon,i)=>(
          <svg key={i} width="18" height="18" viewBox="0 0 24 24">{icon}</svg>
        ))}
      </div>
    </div>
  );
}

/* ─── TikTok (light mode) ─────────────────────────────── */
export function TikTokScreen() {
  const videos = [
    { g: "from-rose-500 to-pink-700", views: "22.2M", pinned: true },
    { g: "from-indigo-500 to-violet-700", views: "39.9M", pinned: true },
    { g: "from-amber-500 to-orange-600", views: "24M", pinned: true },
    { g: "from-teal-500 to-cyan-600", views: "403.2K", pinned: false },
    { g: "from-slate-500 to-gray-700", views: "360.9K", pinned: false },
    { g: "from-purple-500 to-fuchsia-600", views: "652.9K", pinned: false },
  ];

  return (
    <div className="bg-white text-black select-none" style={{ fontSize: 7 }}>
      {/* Status bar */}
      <div className="flex justify-between items-center px-3 pt-2 pb-0.5 text-black" style={{ fontSize: 8, fontWeight: 600 }}>
        <span>8:50</span>
        <div className="flex items-center gap-1">
          <svg width="12" height="8" viewBox="0 0 15 11" fill="black"><rect x="0" y="4" width="3" height="7" rx="0.5"/><rect x="4" y="2.5" width="3" height="8.5" rx="0.5"/><rect x="8" y="1" width="3" height="10" rx="0.5"/></svg>
          <svg width="12" height="8" viewBox="0 0 24 18" fill="black"><path d="M12 3C7.5 3 3.5 4.9.5 8L2 9.5C4.6 7 8.1 5.5 12 5.5s7.4 1.5 10 4L23.5 8C20.5 4.9 16.5 3 12 3z"/><circle cx="12" cy="16" r="2"/></svg>
          <div className="w-4 h-2 border border-black rounded-sm relative"><div className="absolute inset-0.5 right-0.5 bg-black rounded-sm" /></div>
        </div>
      </div>

      {/* Top nav */}
      <div className="flex items-center justify-between px-3 py-1.5">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="black" strokeWidth="2.5"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
        <div />
        <div className="flex gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="black" strokeWidth="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0"/></svg>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="black" strokeWidth="2"><path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8M16 6l-4-4-4 4M12 2v13"/></svg>
        </div>
      </div>

      {/* Avatar */}
      <div className="flex flex-col items-center px-3 pb-2">
        <div className="w-14 h-14 rounded-full bg-gradient-to-br from-pink-400 via-red-500 to-yellow-400 p-[1.5px] mb-1.5">
          <div className="w-full h-full rounded-full bg-gradient-to-br from-orange-300 to-pink-500 border-[1.5px] border-white" />
        </div>

        <div style={{ fontSize: 12, fontWeight: 800, marginBottom: 1 }}>turkervibes</div>
        <div className="flex items-center gap-1 mb-0.5">
          <span style={{ fontSize: 8, color: "#888" }}>@turkervibes</span>
          <Verified size={11} />
        </div>
        <div style={{ fontSize: 7, color: "#aaa", marginBottom: 6 }}>Creator</div>

        {/* Stats */}
        <div className="flex gap-4 mb-2">
          {[["184","Following"],["8.9M","Followers"],["96.4M","Likes"]].map(([n,l])=>(
            <div key={l} className="flex flex-col items-center">
              <span style={{ fontSize: 11, fontWeight: 800, lineHeight: 1.1 }}>{n}</span>
              <span style={{ fontSize: 6.5, color: "#888" }}>{l}</span>
            </div>
          ))}
        </div>

        {/* Buttons */}
        <div className="flex gap-1.5 w-full mb-2">
          <button className="flex-1 rounded-md py-1 text-white font-black" style={{ fontSize: 9, background: "#fe2c55" }}>Follow</button>
          <button className="flex-1 rounded-md py-1 font-bold border border-gray-200" style={{ fontSize: 9, color: "#111" }}>Message</button>
          <button className="rounded-md px-2 py-1 border border-gray-200" style={{ fontSize: 9 }}>▾</button>
        </div>

        <div style={{ fontSize: 7, textAlign: "center", color: "#333", lineHeight: 1.4, marginBottom: 2 }}>
          🎬 Creator · 🌍 Content is king
        </div>
        <div style={{ fontSize: 7, color: "#fe2c55" }}>🔗 turkervibes.com and 2 more</div>
      </div>

      {/* Content tabs */}
      <div className="flex items-center border-b border-gray-200">
        {[
          <svg key="m" width="13" height="13" viewBox="0 0 24 24" fill="#888"><path d="M9 18V5l12-2v13M9 18c0 1.1-.9 2-2 2s-2-.9-2-2 .9-2 2-2 2 .9 2 2zm12-2c0 1.1-.9 2-2 2s-2-.9-2-2 .9-2 2-2 2 .9 2 2z"/></svg>,
          <svg key="g" width="14" height="14" viewBox="0 0 24 24" fill="black"><rect x="3" y="3" width="7" height="7" rx="0.5"/><rect x="14" y="3" width="7" height="7" rx="0.5"/><rect x="3" y="14" width="7" height="7" rx="0.5"/><rect x="14" y="14" width="7" height="7" rx="0.5"/></svg>,
          <svg key="r" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#888" strokeWidth="2"><path d="M1 4v16l6-4 4 4 4-4 6 4V4l-6 4-4-4-4 4-6-4z"/></svg>,
        ].map((icon,i)=>(
          <div key={i} className={`flex-1 flex justify-center py-1.5 ${i===1 ? "border-b-2 border-black" : ""}`}>{icon}</div>
        ))}
      </div>

      {/* Video grid */}
      <div className="grid grid-cols-3 gap-[1px] bg-gray-200">
        {videos.map((v,i)=>(
          <div key={i} className={`aspect-[9/16] bg-gradient-to-br ${v.g} relative overflow-hidden`}>
            {v.pinned && <div className="absolute top-0.5 left-0.5 bg-[#fe2c55] text-white rounded px-0.5" style={{ fontSize: 4, fontWeight: 700 }}>Pinned</div>}
            <div className="absolute inset-0 flex items-center justify-center opacity-50">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="white"><polygon points="5,3 19,12 5,21"/></svg>
            </div>
            <div className="absolute bottom-0.5 left-0.5 flex items-center gap-0.5">
              <svg width="6" height="6" viewBox="0 0 24 24" fill="white"><polygon points="5,3 19,12 5,21"/></svg>
              <span style={{ fontSize: 5, color: "white", fontWeight: 700, textShadow: "0 1px 2px rgba(0,0,0,0.8)" }}>{v.views}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── X / Twitter (dark mode) ────────────────────────── */
export function XScreen() {
  const tweets = [
    { text: "Just wrapped the biggest collab of my career. Can't say who yet but the internet is not ready 👀🔥", likes: "14.2K", rt: "3.8K", img: "from-slate-600 to-gray-800" },
    { text: "Consistency over everything. Posted every day for 365 days. Here's what happened to my numbers 📈", likes: "28.9K", rt: "7.1K", img: null },
  ];

  return (
    <div className="text-white select-none" style={{ background: "#0d0d0d", fontSize: 7 }}>
      {/* Status bar */}
      <div className="flex justify-between items-center px-3 pt-2 pb-0.5" style={{ fontSize: 8, fontWeight: 600 }}>
        <span>10:02</span>
        <div className="flex items-center gap-1">
          <svg width="12" height="8" viewBox="0 0 15 11" fill="white"><rect x="0" y="4" width="3" height="7" rx="0.5"/><rect x="4" y="2.5" width="3" height="8.5" rx="0.5"/><rect x="8" y="1" width="3" height="10" rx="0.5"/></svg>
          <svg width="12" height="8" viewBox="0 0 24 18" fill="white"><path d="M12 3C7.5 3 3.5 4.9.5 8L2 9.5C4.6 7 8.1 5.5 12 5.5s7.4 1.5 10 4L23.5 8C20.5 4.9 16.5 3 12 3z"/><circle cx="12" cy="16" r="2"/></svg>
          <div className="w-4 h-2 border border-white rounded-sm relative"><div className="absolute inset-0.5 right-1 bg-white rounded-sm" /></div>
        </div>
      </div>

      {/* Nav icons */}
      <div className="flex items-center justify-between px-3 py-1.5">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
        <div className="flex gap-2.5">
          {[
            <path key="sync" d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round"/>,
            <><circle key="s" cx="11" cy="11" r="8" stroke="white" strokeWidth="1.5" fill="none"/><path key="sl" d="M21 21l-4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round"/></>,
            <circle key="more" cx="12" cy="12" r="1" fill="white"/>,
          ].map((icon,i)=>(
            <svg key={i} width="14" height="14" viewBox="0 0 24 24">{icon}</svg>
          ))}
        </div>
      </div>

      {/* Banner */}
      <div className="h-14 bg-gradient-to-r from-slate-700 to-slate-900 relative">
        <div className="absolute -bottom-5 left-3 w-10 h-10 rounded-full bg-gradient-to-br from-gray-400 to-gray-600 border-2" style={{ borderColor: "#0d0d0d" }} />
        <div className="absolute bottom-2 right-3">
          <button className="rounded-full px-3 py-1 font-bold border border-white text-white" style={{ fontSize: 7, background: "transparent" }}>Follow</button>
        </div>
      </div>

      <div className="px-3 pt-6 pb-2">
        {/* Display name + verified */}
        <div className="flex items-center gap-1 mb-0.5">
          <span style={{ fontSize: 11, fontWeight: 800 }}>TurkerVibes</span>
          <Verified size={13} />
        </div>
        <div style={{ fontSize: 8, color: "#888", marginBottom: 4 }}>@TurkerVibes</div>
        <div style={{ fontSize: 7.5, color: "#e7e9ea", lineHeight: 1.4, marginBottom: 4 }}>
          Creating content that hits different. Social media strategist &amp; creator 🎯
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 mb-2" style={{ fontSize: 7, color: "#888" }}>
          <span>📍 Lagos, Nigeria</span>
          <span style={{ color: "#1d9bf0" }}>🔗 turkervibes.com</span>
          <span>📅 Joined March 2019</span>
        </div>
        <div className="flex gap-3 mb-1" style={{ fontSize: 7.5 }}>
          <span><b>3.8K</b> <span style={{ color: "#888" }}>Following</span></span>
          <span><b>35.7K</b> <span style={{ color: "#888" }}>Followers</span></span>
        </div>
        <div style={{ fontSize: 7, color: "#888", marginBottom: 6 }}>
          Followed by creator.hub, viral.studio and 3 others
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b" style={{ borderColor: "#2f3336" }}>
        {["Posts","Replies","Videos","Photos"].map((t,i)=>(
          <div key={t} className="flex-1 text-center py-1.5" style={{ fontSize: 7.5, fontWeight: 700, color: i===0 ? "white" : "#888", borderBottom: i===0 ? "2px solid #1d9bf0" : "none" }}>{t}</div>
        ))}
      </div>

      {/* Tweets */}
      {tweets.map((tw,i)=>(
        <div key={i} className="px-3 py-2 border-b" style={{ borderColor: "#2f3336" }}>
          <div className="flex gap-2">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-gray-400 to-gray-600 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1 mb-0.5 flex-wrap">
                <span style={{ fontSize: 7.5, fontWeight: 700 }}>TurkerVibes</span>
                <Verified size={9} />
                <span style={{ fontSize: 6.5, color: "#888" }}>@TurkerVibes · 3h</span>
              </div>
              <p style={{ fontSize: 7, lineHeight: 1.4, color: "#e7e9ea", marginBottom: 4 }}>{tw.text}</p>
              {tw.img && <div className={`w-full h-14 rounded-lg bg-gradient-to-br ${tw.img} mb-1`} />}
              <div className="flex gap-3" style={{ fontSize: 6.5, color: "#888" }}>
                <span>💬 {Math.floor(parseInt(tw.likes)*0.03/100)*100 || 412}</span>
                <span>🔁 {tw.rt}</span>
                <span>❤️ {tw.likes}</span>
                <span>📊 {parseInt(tw.likes.replace("K",""))*40}K</span>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ─── Layout ──────────────────────────────────────────── */
function Screen({ children, rotate, translateY, glow }: { children: React.ReactNode; rotate?: string; translateY?: string; glow?: string }) {
  return (
    <div
      className="relative flex-shrink-0 hover:scale-[1.03] transition-transform duration-300"
      style={{ transform: `rotate(${rotate ?? "0deg"}) translateY(${translateY ?? "0"})` }}
    >
      {glow && <div className="absolute -inset-3 rounded-3xl blur-2xl opacity-30 pointer-events-none" style={{ background: glow }} />}
      <div className="relative rounded-3xl overflow-hidden shadow-[0_32px_64px_rgba(0,0,0,0.7)] border border-white/10" style={{ width: 180, height: 380 }}>
        {children}
      </div>
    </div>
  );
}

/* The screens are authored at a native 180×380; ScreenFrame renders one in a rounded,
   case-less frame scaled to any width (same look the landing page uses). */
const NATIVE_W = 180;
const NATIVE_H = 380;

export function ScreenFrame({ children, width = 180 }: { children: React.ReactNode; width?: number }) {
  const scale = width / NATIVE_W;
  return (
    <div
      className="relative rounded-3xl overflow-hidden shadow-[0_24px_48px_rgba(0,0,0,0.5)] border border-white/10"
      style={{ width, height: NATIVE_H * scale }}
    >
      <div style={{ width: NATIVE_W, height: NATIVE_H, transform: `scale(${scale})`, transformOrigin: "top left" }}>
        {children}
      </div>
    </div>
  );
}

export const PROFILE_SCREENS = [
  { platform: "Instagram", Screen: InstagramScreen },
  { platform: "X", Screen: XScreen },
  { platform: "TikTok", Screen: TikTokScreen },
] as const;

export function PhoneMockups() {
  return (
    <div className="relative w-full max-w-3xl mx-auto mt-4 mb-6">
      <div className="flex items-end justify-center gap-5">
        <Screen rotate="-5deg" translateY="28px">
          <InstagramScreen />
        </Screen>
        <Screen glow="linear-gradient(135deg,hsl(190 90% 50%),hsl(280 80% 60%))" rotate="0deg">
          <XScreen />
        </Screen>
        <Screen rotate="5deg" translateY="28px">
          <TikTokScreen />
        </Screen>
      </div>

      <div className="flex justify-center gap-5 mt-5">
        <div className="w-[180px] text-center text-[9px] font-bold uppercase tracking-widest text-muted-foreground/50" style={{ transform: "rotate(-5deg)" }}>Instagram</div>
        <div className="w-[180px] text-center text-[9px] font-bold uppercase tracking-widest text-primary/60">X</div>
        <div className="w-[180px] text-center text-[9px] font-bold uppercase tracking-widest text-muted-foreground/50" style={{ transform: "rotate(5deg)" }}>TikTok</div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-background to-transparent pointer-events-none" />
    </div>
  );
}
