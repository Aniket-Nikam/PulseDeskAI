import React, { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";

/* ─── Intersection Observer hook ────────────────────────────────────────── */
function useReveal(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null);
  const [v, setV] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setV(true); obs.unobserve(el); } },
      { threshold },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible: v };
}

/* ─── Animated counter ──────────────────────────────────────────────────── */
function AnimatedNum({ end, suffix = "", duration = 2000 }: { end: number; suffix?: string; duration?: number }) {
  const [val, setVal] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !started.current) {
        started.current = true;
        const start = performance.now();
        const tick = (now: number) => {
          const p = Math.min((now - start) / duration, 1);
          const ease = 1 - Math.pow(1 - p, 3);
          setVal(Math.round(end * ease));
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }
    }, { threshold: 0.3 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [end, duration]);

  return <span ref={ref}>{val.toLocaleString()}{suffix}</span>;
}

/* ─── LANDING PAGE ──────────────────────────────────────────────────────── */
export function LandingPage() {
  const [isAnnual, setIsAnnual] = useState(false);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);
  const [activeStep, setActiveStep] = useState(0);
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("pd-landing-theme");
      if (saved) return saved === "dark";
      return true; // dark by default
    }
    return true;
  });
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);

  const toggleTheme = () => {
    setIsDark(p => { const n = !p; localStorage.setItem("pd-landing-theme", n ? "dark" : "light"); return n; });
  };

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  useEffect(() => {
    const t = setInterval(() => setActiveStep(s => (s + 1) % 3), 5000);
    return () => clearInterval(t);
  }, []);

  const toggleFaq = (i: number) => setActiveFaq(activeFaq === i ? null : i);
  const proPrice = isAnnual ? 6.40 : 8;
  const eduPrice = isAnnual ? 2.40 : 3;

  const r1 = useReveal(); const r2 = useReveal(); const r3 = useReveal();
  const r4 = useReveal(); const r5 = useReveal(); const r6 = useReveal();
  const r7 = useReveal(); const r8 = useReveal();

  const tc = isDark ? "lp-dark" : "lp-light";

  return (
    <div className={`lp ${tc}`}>
      {/* ── NAV ─────────────────────────────────────────────────────── */}
      <nav className={`lp-nav ${scrolled ? "scrolled" : ""}`}>
        <div className="lp-w lp-nav-inner">
          <Link to="/" className="lp-brand">
            <span className="lp-brand-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            </span>
            PulseDesk
          </Link>
          <div className="lp-nav-links">
            <a href="#features">Features</a>
            <a href="#pricing">Pricing</a>
            <a href="#how-it-works">Setup</a>
            <a href="#faq">FAQ</a>
          </div>
          <div className="lp-nav-right">
            <button className="lp-theme-btn" onClick={toggleTheme} aria-label="Toggle theme">
              {isDark ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
              )}
            </button>
            <Link to="/login" className="lp-btn lp-btn-ghost">Sign in</Link>
            <Link to="/signup" className="lp-btn lp-btn-primary">Get Started Free</Link>
          </div>
          <button className="lp-burger" onClick={() => setMobileMenu(!mobileMenu)} aria-label="Menu">
            <span/><span/><span/>
          </button>
        </div>
        {mobileMenu && (
          <div className="lp-mobile-menu">
            <a href="#features" onClick={() => setMobileMenu(false)}>Features</a>
            <a href="#pricing" onClick={() => setMobileMenu(false)}>Pricing</a>
            <a href="#how-it-works" onClick={() => setMobileMenu(false)}>Setup</a>
            <a href="#faq" onClick={() => setMobileMenu(false)}>FAQ</a>
            <div style={{display:"flex",gap:8,marginTop:8}}>
              <Link to="/login" className="lp-btn lp-btn-ghost" style={{flex:1,justifyContent:"center"}}>Sign in</Link>
              <Link to="/signup" className="lp-btn lp-btn-primary" style={{flex:1,justifyContent:"center"}}>Get Started</Link>
            </div>
          </div>
        )}
      </nav>

      {/* ── HERO ────────────────────────────────────────────────────── */}
      <section className="lp-hero">
        <div className="lp-hero-bg" aria-hidden="true"/>
        <div ref={r1.ref} className={`lp-w lp-hero-inner ${r1.visible?"reveal":""}`}>
          <div className="lp-chip">
            <span className="lp-chip-dot"/>Self-Hosted &middot; Open Source &middot; GDPR-Ready
          </div>
          <h1>Secure Analytics.<br/>Know Your Team's <span className="lp-grad">Pulse</span>.</h1>
          <p className="lp-hero-sub">
            Premium, self-hosted employee activity and productivity tracking.
            AI-powered insights with complete data sovereignty — no data ever leaves your servers.
          </p>
          <div className="lp-hero-actions">
            <Link to="/signup" className="lp-btn lp-btn-primary lp-btn-lg">
              Start Free — No Credit Card
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </Link>
            <a href="#features" className="lp-btn lp-btn-sec lp-btn-lg">See How It Works</a>
          </div>

          {/* Trust bar */}
          <div className="lp-trust">
            <div className="lp-trust-item"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> SOC 2 Ready</div>
            <div className="lp-trust-item"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> End-to-End Encrypted</div>
            <div className="lp-trust-item"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg> GDPR Compliant</div>
            <div className="lp-trust-item"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 12l2 2 4-4"/></svg> 99.9% Uptime</div>
          </div>

          {/* Dashboard Preview */}
          <div className="lp-preview">
            <div className="lp-preview-chrome">
              <div className="lp-dots"><span/><span/><span/></div>
              <div className="lp-preview-url">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                pulsedesk.local/dashboard
              </div>
              <div style={{width:52}}/>
            </div>
            <div className="lp-preview-body">
              <div className="lp-preview-side">
                <div className="lp-ps-user"><div className="lp-ps-av">AN</div><div><div className="lp-ps-name">Nikam Aniket</div><div className="lp-ps-status"><span/>Active</div></div></div>
                <div className="lp-ps-menu">
                  <div className="lp-ps-item active">📈 Live Overview</div>
                  <div className="lp-ps-item">🖥️ Screen Streams</div>
                  <div className="lp-ps-item">🤖 AI Insights</div>
                  <div className="lp-ps-item">⚠️ Anomalies</div>
                  <div className="lp-ps-item">📊 Analytics</div>
                  <div className="lp-ps-item">📸 Screenshots</div>
                  <div className="lp-ps-item">⚙️ Settings</div>
                </div>
              </div>
              <div className="lp-preview-main">
                <div className="lp-pm-topbar">
                  <span className="lp-pm-greeting">Good afternoon, Aniket</span>
                  <span className="lp-pm-date">June 17, 2026</span>
                </div>
                <div className="lp-pm-stats">
                  <div className="lp-pm-stat"><div className="lp-pm-sl">FOCUS SCORE</div><div className="lp-pm-sv" style={{color:"var(--lp-green)"}}>94%</div><div className="lp-pm-sc">↑ 3.2% from last week</div></div>
                  <div className="lp-pm-stat"><div className="lp-pm-sl">ACTIVE HOURS</div><div className="lp-pm-sv">6h 42m</div><div className="lp-pm-sc">Across 12 employees</div></div>
                  <div className="lp-pm-stat"><div className="lp-pm-sl">IDLE TIME</div><div className="lp-pm-sv" style={{color:"var(--lp-amber)"}}>12m</div><div className="lp-pm-sc">↓ 8% improvement</div></div>
                  <div className="lp-pm-stat"><div className="lp-pm-sl">ANOMALIES</div><div className="lp-pm-sv" style={{color:"var(--lp-red)"}}>3</div><div className="lp-pm-sc">2 after-hours, 1 idle</div></div>
                </div>
                <div className="lp-pm-chart">
                  <div className="lp-pm-chart-title">Productivity Trend — This Week</div>
                  <svg viewBox="0 0 500 100" preserveAspectRatio="none">
                    <defs><linearGradient id="cg1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--lp-accent)" stopOpacity="0.25"/><stop offset="100%" stopColor="var(--lp-accent)" stopOpacity="0"/></linearGradient></defs>
                    <path d="M0,80 C40,70 80,30 140,45 S220,15 280,30 S360,8 420,18 S480,5 500,10 L500,100 L0,100Z" fill="url(#cg1)"/>
                    <path className="lp-chart-line" d="M0,80 C40,70 80,30 140,45 S220,15 280,30 S360,8 420,18 S480,5 500,10"/>
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── STATS BAR ───────────────────────────────────────────────── */}
      <section className="lp-stats-bar">
        <div ref={r2.ref} className={`lp-w lp-stats-inner ${r2.visible?"reveal":""}`}>
          <div className="lp-stat-block"><div className="lp-stat-num"><AnimatedNum end={2500} suffix="+"/></div><div className="lp-stat-label">Active Deployments</div></div>
          <div className="lp-stat-divider"/>
          <div className="lp-stat-block"><div className="lp-stat-num"><AnimatedNum end={50000} suffix="+"/></div><div className="lp-stat-label">Employees Monitored</div></div>
          <div className="lp-stat-divider"/>
          <div className="lp-stat-block"><div className="lp-stat-num"><AnimatedNum end={99} suffix=".9%"/></div><div className="lp-stat-label">Uptime Guarantee</div></div>
          <div className="lp-stat-divider"/>
          <div className="lp-stat-block"><div className="lp-stat-num"><AnimatedNum end={4} suffix=".9★"/></div><div className="lp-stat-label">User Rating</div></div>
        </div>
      </section>

      {/* ── FEATURES BENTO ──────────────────────────────────────────── */}
      <section className="lp-section" id="features">
        <div ref={r3.ref} className={`lp-w ${r3.visible?"reveal":""}`}>
          <div className="lp-sh">
            <span className="lp-overline">Capabilities</span>
            <h2>Everything you need to monitor, analyze, and optimize your workforce.</h2>
            <p>Built from the ground up for privacy-conscious organizations that refuse to compromise on insights.</p>
          </div>
          <div className="lp-bento">
            <div className="lp-bento-card lp-bento-wide">
              <div className="lp-bc-content">
                <div className="lp-bc-icon">📊</div>
                <h3>Real-Time Live Feed</h3>
                <p>WebSocket-powered activity stream with live employee status, active window titles, focus indicators, and instant alerts. See who's working on what — right now.</p>
              </div>
              <div className="lp-bc-visual lp-bc-v1">
                <div className="lp-live-row"><span className="lp-live-dot green"/>Sarah K. — VS Code<span className="lp-live-tag">Focused</span></div>
                <div className="lp-live-row"><span className="lp-live-dot green"/>James M. — Figma<span className="lp-live-tag">Active</span></div>
                <div className="lp-live-row"><span className="lp-live-dot amber"/>Priya R. — Chrome<span className="lp-live-tag warn">Browsing</span></div>
                <div className="lp-live-row"><span className="lp-live-dot red"/>Tom B. — Idle 8m<span className="lp-live-tag danger">Idle</span></div>
              </div>
            </div>
            <div className="lp-bento-card">
              <div className="lp-bc-icon">🤖</div>
              <h3>AI Chat Analyst</h3>
              <p>Ask questions in plain English. Get instant insights on burnout risk, team performance, and productivity bottlenecks — powered by Llama &amp; Groq AI.</p>
              <div className="lp-bc-visual lp-bc-v2">
                <div className="lp-chat-bubble user">"Who's at burnout risk this week?"</div>
                <div className="lp-chat-bubble ai">Based on overtime patterns, James M. worked 12h+ for 3 consecutive days. Consider a check-in.</div>
              </div>
            </div>
            <div className="lp-bento-card">
              <div className="lp-bc-icon">🔍</div>
              <h3>Anomaly Detection</h3>
              <p>Rule-based engine flags excessive idle time, rapid app switching, after-hours activity, and policy violations — with zero false positives.</p>
              <div className="lp-bc-visual lp-bc-v3">
                <div className="lp-anomaly-row"><span className="lp-a-badge warn">⚠️ IDLE</span>Tom B. — 8 min idle detected</div>
                <div className="lp-anomaly-row"><span className="lp-a-badge danger">🚫 AFTER-HRS</span>Login at 11:42 PM</div>
              </div>
            </div>
            <div className="lp-bento-card">
              <div className="lp-bc-icon">📸</div>
              <h3>Smart Screenshots</h3>
              <p>Configurable capture schedules with anomaly-triggered recording. Full admin access control and encrypted on-premise storage.</p>
            </div>
            <div className="lp-bento-card">
              <div className="lp-bc-icon">🚫</div>
              <h3>Website Blocker</h3>
              <p>Centrally manage blocked domains across all devices. Auto-captures visual proof of any browser violation events.</p>
            </div>
            <div className="lp-bento-card">
              <div className="lp-bc-icon">📄</div>
              <h3>PDF Reporting</h3>
              <p>Generate print-ready daily summaries, department comparisons, and weekly focus score trends for leadership reviews.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── SOCIAL PROOF ────────────────────────────────────────────── */}
      <section className="lp-section lp-section-alt">
        <div ref={r4.ref} className={`lp-w ${r4.visible?"reveal":""}`}>
          <div className="lp-sh">
            <span className="lp-overline">Trusted By</span>
            <h2>Used by teams that value privacy.</h2>
          </div>
          <div className="lp-testimonials">
            <div className="lp-testimonial-card">
              <div className="lp-tc-stars">★★★★★</div>
              <p>"PulseDesk gave us full visibility into remote team productivity without sacrificing employee trust. The self-hosted model was the deciding factor."</p>
              <div className="lp-tc-author">
                <div className="lp-tc-av">RK</div>
                <div><div className="lp-tc-name">Rohit Kumar</div><div className="lp-tc-role">CTO, DataSync Labs</div></div>
              </div>
            </div>
            <div className="lp-testimonial-card">
              <div className="lp-tc-stars">★★★★★</div>
              <p>"We deployed PulseDesk across 200 lab computers for exam proctoring. The domain blocker and screenshot features are exactly what we needed."</p>
              <div className="lp-tc-author">
                <div className="lp-tc-av">AP</div>
                <div><div className="lp-tc-name">Dr. Anita Patel</div><div className="lp-tc-role">Dean of IT, VJTI Mumbai</div></div>
              </div>
            </div>
            <div className="lp-testimonial-card">
              <div className="lp-tc-stars">★★★★★</div>
              <p>"The AI chat analyst is a game-changer. I can ask 'who's struggling this sprint?' and get actionable answers in seconds. Brilliant product."</p>
              <div className="lp-tc-author">
                <div className="lp-tc-av">MS</div>
                <div><div className="lp-tc-name">Michael Schneider</div><div className="lp-tc-role">Engineering Manager, Codex AG</div></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── PRICING ─────────────────────────────────────────────────── */}
      <section className="lp-section" id="pricing">
        <div ref={r5.ref} className={`lp-w ${r5.visible?"reveal":""}`}>
          <div className="lp-sh">
            <span className="lp-overline">Pricing</span>
            <h2>Simple, transparent pricing.</h2>
            <p>Start with our free self-hosted edition. Scale when you're ready.</p>
          </div>
          <div className="lp-price-toggle">
            <span className={!isAnnual?"active":""} onClick={() => setIsAnnual(false)} style={{cursor:"pointer"}}>Monthly</span>
            <button className={`lp-switch ${isAnnual?"on":""}`} onClick={() => setIsAnnual(!isAnnual)} aria-label="Toggle billing"><span className="lp-switch-thumb"/></button>
            <span className={isAnnual?"active":""} onClick={() => setIsAnnual(true)} style={{cursor:"pointer"}}>Annually</span>
            <span className="lp-save-pill">Save 20%</span>
          </div>
          <div className="lp-pricing-grid">
            <div className="lp-price-card">
              <div className="lp-pc-tier">Community</div>
              <div className="lp-pc-price">$0<span>/month</span></div>
              <p className="lp-pc-desc">For small teams getting started with self-hosted monitoring.</p>
              <ul><li>Up to 5 employees</li><li>Real-time dashboard</li><li>Basic anomaly detection</li><li>Self-hosted database</li><li>Community forum support</li></ul>
              <Link to="/signup" state={{plan:"community"}} className="lp-btn lp-btn-sec lp-btn-full">Get Started Free</Link>
            </div>
            <div className="lp-price-card featured">
              <div className="lp-pc-badge">Most Popular</div>
              <div className="lp-pc-tier">Pro</div>
              <div className="lp-pc-price">${proPrice.toFixed(2)}<span>/user/mo</span></div>
              <p className="lp-pc-desc">Full analytics suite with AI insights and advanced monitoring.</p>
              <ul><li>Unlimited employees</li><li>AI chat analyst &amp; recommendations</li><li>Configurable screenshot intervals</li><li>Advanced PDF report generation</li><li>Granular department management</li><li>Priority email support</li></ul>
              <Link to="/signup" state={{plan:"pro"}} className="lp-btn lp-btn-primary lp-btn-full">Start 14-Day Free Trial</Link>
            </div>
            <div className="lp-price-card">
              <div className="lp-pc-tier">Education</div>
              <div className="lp-pc-price">${eduPrice.toFixed(2)}<span>/seat/mo</span></div>
              <p className="lp-pc-desc">Built for university labs, exam proctoring, and classrooms.</p>
              <ul><li>Unlimited lab devices</li><li>High-FPS proctoring mode</li><li>Exam domain blocklists</li><li>Automated attendance</li><li>Bulk deployment scripts</li><li>Phone &amp; email support</li></ul>
              <Link to="/signup" state={{plan:"education"}} className="lp-btn lp-btn-sec lp-btn-full">Contact Sales</Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ────────────────────────────────────────────── */}
      <section className="lp-section lp-section-alt" id="how-it-works">
        <div ref={r6.ref} className={`lp-w ${r6.visible?"reveal":""}`}>
          <div className="lp-sh">
            <span className="lp-overline">Quick Start</span>
            <h2>Deploy in under 5 minutes.</h2>
            <p>Three steps from zero to full monitoring. No DevOps expertise required.</p>
          </div>
          <div className="lp-tut-grid">
            <div className="lp-tut-tabs">
              {[
                {n:"01",title:"Create Admin Account",sub:"Set up your organization"},
                {n:"02",title:"Deploy the Backend",sub:"Docker or one-click launcher"},
                {n:"03",title:"Enroll Employee Devices",sub:"Install agent & start monitoring"},
              ].map((s,i) => (
                <button key={i} className={`lp-tut-tab ${activeStep===i?"active":""}`} onClick={() => setActiveStep(i)}>
                  <span className="lp-tut-num">{s.n}</span>
                  <div><div className="lp-tut-title">{s.title}</div><div className="lp-tut-sub">{s.sub}</div></div>
                  {activeStep===i && <div className="lp-tut-progress"><div className="lp-tut-progress-fill"/></div>}
                </button>
              ))}
            </div>
            <div className="lp-tut-content">
              {activeStep === 0 && (
                <div className="lp-tut-fade" key="s0">
                  <h3>Set up your PulseDesk admin space</h3>
                  <p>Register with your business or school name, email, and a strong passphrase. You'll be the Super Admin — the only person with access to employee activity data.</p>
                  <div className="lp-tut-highlight">
                    <strong>🔒 Security First</strong> — Passwords are hashed with bcrypt. All data stays on your server. No external transmission whatsoever.
                  </div>
                  <div className="lp-tut-mockup">
                    <div className="lp-tm-field"><span>Organization</span><div>Acme Corp</div></div>
                    <div className="lp-tm-field"><span>Admin Email</span><div>admin@acme.com</div></div>
                    <div className="lp-tm-field"><span>Password</span><div>••••••••••••</div></div>
                    <div className="lp-tm-field"><span>Account Type</span><div className="lp-tm-locked">🔒 Admin (locked)</div></div>
                  </div>
                  <Link to="/signup" state={{plan:"pro"}} className="lp-btn lp-btn-primary" style={{marginTop:20}}>
                    Create Admin Account →
                  </Link>
                </div>
              )}
              {activeStep === 1 && (
                <div className="lp-tut-fade" key="s1">
                  <h3>Deploy your backend server</h3>
                  <p>Run the entire PulseDesk stack using Docker Compose or our one-click Windows launcher. Takes under 2 minutes.</p>
                  <div className="lp-code-block">
                    <div className="lp-code-head"><span>terminal</span><span className="lp-code-copy">$ docker compose</span></div>
                    <pre>{`$ docker compose up -d
✔ Container pulsedesk-db      Started
✔ Container pulsedesk-server   Started  
✔ Container pulsedesk-frontend  Started

Dashboard → http://localhost:5173
API       → http://localhost:8000`}</pre>
                  </div>
                  <p style={{marginTop:16,fontSize:13,color:"var(--lp-muted)"}}>
                    <strong>Windows users:</strong> Simply double-click <code>RUN_PULSEDESK.bat</code> — it auto-configures PostgreSQL, environment variables, and launches everything.
                  </p>
                </div>
              )}
              {activeStep === 2 && (
                <div className="lp-tut-fade" key="s2">
                  <h3>Enroll employee machines</h3>
                  <p>From the admin dashboard, generate a unique invitation code for each employee. They run a one-line installer and monitoring begins automatically.</p>
                  <div className="lp-invite-card">
                    <div className="lp-invite-label">INVITATION CODE</div>
                    <div className="lp-invite-code">PD-9A7-3B3</div>
                    <div className="lp-invite-steps">
                      <div className="lp-invite-step"><span>1</span> Employee opens enrollment page</div>
                      <div className="lp-invite-step"><span>2</span> Enters invitation code</div>
                      <div className="lp-invite-step"><span>3</span> Downloads &amp; runs <code>INSTALL_AGENT.bat</code></div>
                      <div className="lp-invite-step"><span>4</span> ✅ Telemetry syncs automatically</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────────────── */}
      <section className="lp-section" id="faq">
        <div ref={r7.ref} className={`lp-w ${r7.visible?"reveal":""}`}>
          <div className="lp-sh">
            <span className="lp-overline">FAQ</span>
            <h2>Frequently asked questions.</h2>
            <p>Everything you need to know about PulseDesk's privacy model, hosting, and capabilities.</p>
          </div>
          <div className="lp-faq-list">
            {[
              {q:"Is my data shared with PulseDesk servers?",a:"Absolutely not. PulseDesk is 100% self-hosted. The entire stack — database, API, and dashboard — runs inside your own network. No telemetry, metadata, or activity logs ever leave your infrastructure. You own every byte."},
              {q:"How do client devices sync with the server?",a:"Enrolled devices run a lightweight background agent (< 15MB RAM) that syncs domain blocklists, screenshot schedules, and activity telemetry via encrypted HTTPS and WebSocket connections to your server."},
              {q:"Can employees manage their own consent?",a:"Yes. PulseDesk includes a full employee portal where users can view their own activity timeline, manage GDPR Article 7 monitoring consent, and export their complete data profile per Article 15 (right of access)."},
              {q:"What are the hosting requirements?",a:"Any server with Docker support. The compose stack deploys a FastAPI backend, React frontend, and PostgreSQL database. Minimum: 2 CPU cores, 4GB RAM. Works on Linux, Windows Server, or macOS."},
              {q:"How is PulseDesk different from competitors?",a:"Unlike cloud-based tools (Hubstaff, Time Doctor), PulseDesk runs entirely on your infrastructure. No per-seat cloud costs, no data leaving your network, and full customization through the open-source codebase. Plus, built-in AI analysis."},
              {q:"Is there a free tier?",a:"Yes! The Community plan is completely free for teams up to 5 employees. It includes real-time dashboards, basic anomaly detection, and community support. No credit card required, no time limits."},
            ].map((f,i) => (
              <div className={`lp-faq-item ${activeFaq===i?"open":""}`} key={i}>
                <button className="lp-faq-q" onClick={() => toggleFaq(i)}>
                  <span>{f.q}</span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lp-faq-chev"><polyline points="6 9 12 15 18 9"/></svg>
                </button>
                <div className="lp-faq-a" style={{maxHeight:activeFaq===i?300:0,paddingBottom:activeFaq===i?20:0}}>{f.a}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ───────────────────────────────────────────────── */}
      <section className="lp-cta">
        <div className="lp-cta-bg" aria-hidden="true"/>
        <div ref={r8.ref} className={`lp-w lp-cta-inner ${r8.visible?"reveal":""}`}>
          <h2>Ready to take control of<br/>your team's productivity?</h2>
          <p>Deploy your private analytics stack in under 5 minutes. Free forever for small teams.</p>
          <div className="lp-hero-actions">
            <Link to="/signup" className="lp-btn lp-btn-primary lp-btn-lg lp-btn-glow">
              Get Started Free →
            </Link>
            <Link to="/signup" state={{plan:"pro"}} className="lp-btn lp-btn-sec lp-btn-lg">Book a Demo</Link>
          </div>
          <div className="lp-cta-note">No credit card required · Free community tier · Self-hosted</div>
        </div>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────────────── */}
      <footer className="lp-footer">
        <div className="lp-w lp-footer-inner">
          <div className="lp-footer-top">
            <div className="lp-footer-brand">
              <div className="lp-brand" style={{marginBottom:12}}>
                <span className="lp-brand-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></span>
                PulseDesk
              </div>
              <p>Privacy-first employee activity analytics. Self-hosted, open source, GDPR-compliant.</p>
            </div>
            <div className="lp-footer-col">
              <h4>Product</h4>
              <a href="#features">Features</a>
              <a href="#pricing">Pricing</a>
              <a href="#how-it-works">Setup Guide</a>
              <a href="#faq">FAQ</a>
            </div>
            <div className="lp-footer-col">
              <h4>Resources</h4>
              <a href="#how-it-works">Documentation</a>
              <a href="#faq">API Reference</a>
              <a href="#faq">Changelog</a>
              <a href="#faq">Status Page</a>
            </div>
            <div className="lp-footer-col">
              <h4>Legal</h4>
              <a href="#faq">Privacy Policy</a>
              <a href="#faq">Terms of Service</a>
              <a href="#faq">GDPR Compliance</a>
              <a href="#faq">Security</a>
            </div>
          </div>
          <div className="lp-footer-bottom">
            <p>© {new Date().getFullYear()} PulseDesk. All rights reserved. Built with security-first engineering.</p>
          </div>
        </div>
      </footer>

      <style dangerouslySetInnerHTML={{__html: CSS}}/>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════════
   CSS
   ════════════════════════════════════════════════════════════════════════════ */
const CSS = `
/* ── TOKENS ───────────────────────────────────────────────────────────────── */
.lp{--lp-font:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--lp-display:'Outfit','Inter',sans-serif;--lp-max:1140px;--lp-r:14px;--lp-rs:8px;--lp-ease:cubic-bezier(.16,1,.3,1);font-family:var(--lp-font);min-height:100vh;overflow-x:hidden;-webkit-font-smoothing:antialiased}

.lp.lp-dark{--lp-bg:#050505;--lp-bg2:#0a0a0a;--lp-bg3:#111;--lp-card:rgba(255,255,255,.04);--lp-card-h:rgba(255,255,255,.07);--lp-text:#f5f5f7;--lp-muted:#86868b;--lp-dim:#48484a;--lp-border:rgba(255,255,255,.08);--lp-border-h:rgba(255,255,255,.15);--lp-accent:#2997ff;--lp-accent-h:#40a9ff;--lp-accent-glow:rgba(41,151,255,.12);--lp-green:#34d399;--lp-amber:#fbbf24;--lp-red:#f87171;--lp-nav-bg:rgba(5,5,5,.8);--lp-code:#111;--lp-alt:#080808;background:var(--lp-bg);color:var(--lp-text)}
.lp.lp-light{--lp-bg:#fff;--lp-bg2:#fafafa;--lp-bg3:#f0f0f0;--lp-card:rgba(0,0,0,.03);--lp-card-h:rgba(0,0,0,.06);--lp-text:#1d1d1f;--lp-muted:#6e6e73;--lp-dim:#aeaeb2;--lp-border:rgba(0,0,0,.1);--lp-border-h:rgba(0,0,0,.18);--lp-accent:#0071e3;--lp-accent-h:#0077ed;--lp-accent-glow:rgba(0,113,227,.08);--lp-green:#059669;--lp-amber:#d97706;--lp-red:#dc2626;--lp-nav-bg:rgba(255,255,255,.85);--lp-code:#f5f5f7;--lp-alt:#f5f5f7;background:var(--lp-bg);color:var(--lp-text)}

/* ── UTILS ────────────────────────────────────────────────────────────────── */
.lp-w{max-width:var(--lp-max);margin:0 auto;padding:0 24px;width:100%}
.lp-w:not(.reveal),.lp-hero-inner:not(.reveal),.lp-cta-inner:not(.reveal),.lp-stats-inner:not(.reveal){opacity:0;transform:translateY(32px)}
.reveal{opacity:1!important;transform:translateY(0)!important;transition:opacity .7s var(--lp-ease),transform .7s var(--lp-ease)}

/* ── NAV ──────────────────────────────────────────────────────────────────── */
.lp-nav{position:fixed;top:0;left:0;right:0;z-index:1000;height:56px;display:flex;align-items:center;transition:all .3s}
.lp-nav.scrolled{background:var(--lp-nav-bg);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);border-bottom:1px solid var(--lp-border)}
.lp-nav-inner{display:flex;align-items:center;justify-content:space-between}
.lp-brand{display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--lp-text);font-family:var(--lp-display);font-size:17px;font-weight:700;letter-spacing:-.02em}
.lp-brand-icon{width:28px;height:28px;border-radius:7px;background:var(--lp-accent);display:flex;align-items:center;justify-content:center;color:#fff;flex-shrink:0}
.lp-brand-icon svg{width:14px;height:14px}
.lp-nav-links{display:flex;gap:28px}
.lp-nav-links a{font-size:13px;font-weight:500;color:var(--lp-muted);text-decoration:none;transition:color .2s}
.lp-nav-links a:hover{color:var(--lp-text)}
.lp-nav-right{display:flex;align-items:center;gap:10px}
.lp-theme-btn{background:var(--lp-card);border:1px solid var(--lp-border);border-radius:8px;width:34px;height:34px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:var(--lp-muted);transition:all .2s}
.lp-theme-btn:hover{color:var(--lp-text);border-color:var(--lp-border-h);background:var(--lp-card-h)}
.lp-burger{display:none;background:none;border:none;cursor:pointer;padding:4px;flex-direction:column;gap:4px}
.lp-burger span{display:block;width:18px;height:2px;background:var(--lp-text);border-radius:1px}
.lp-mobile-menu{position:absolute;top:56px;left:0;right:0;background:var(--lp-bg);border-bottom:1px solid var(--lp-border);padding:16px 24px;display:flex;flex-direction:column;gap:12px}
.lp-mobile-menu a{font-size:14px;color:var(--lp-muted);text-decoration:none;padding:8px 0}

/* ── BTNS ─────────────────────────────────────────────────────────────────── */
.lp-btn{display:inline-flex;align-items:center;gap:6px;padding:9px 20px;border-radius:980px;font-size:13px;font-weight:600;font-family:var(--lp-font);text-decoration:none;border:none;cursor:pointer;transition:all .2s var(--lp-ease);white-space:nowrap}
.lp-btn-primary{background:var(--lp-accent);color:#fff}
.lp-btn-primary:hover{background:var(--lp-accent-h);transform:translateY(-1px);box-shadow:0 4px 20px var(--lp-accent-glow)}
.lp-btn-sec{background:var(--lp-card);color:var(--lp-text);border:1px solid var(--lp-border)}
.lp-btn-sec:hover{background:var(--lp-card-h);border-color:var(--lp-border-h)}
.lp-btn-ghost{background:transparent;color:var(--lp-muted)}
.lp-btn-ghost:hover{color:var(--lp-text)}
.lp-btn-lg{padding:13px 28px;font-size:15px}
.lp-btn-full{width:100%;justify-content:center;margin-top:auto}
.lp-btn-glow{box-shadow:0 0 40px var(--lp-accent-glow),0 4px 20px var(--lp-accent-glow)}

/* ── HERO ─────────────────────────────────────────────────────────────────── */
.lp-hero{padding:120px 0 60px;position:relative;text-align:center;overflow:hidden}
.lp-hero-bg{position:absolute;top:-200px;left:50%;transform:translateX(-50%);width:1000px;height:700px;background:radial-gradient(ellipse,var(--lp-accent-glow) 0%,transparent 65%);pointer-events:none;z-index:0}
.lp-hero-inner{position:relative;z-index:1}
.lp-chip{display:inline-flex;align-items:center;gap:8px;padding:6px 16px;border-radius:980px;font-size:12px;font-weight:500;color:var(--lp-muted);background:var(--lp-card);border:1px solid var(--lp-border);margin-bottom:28px}
.lp-chip-dot{width:6px;height:6px;border-radius:50%;background:var(--lp-green);box-shadow:0 0 8px var(--lp-green);flex-shrink:0}
.lp-hero h1{font-family:var(--lp-display);font-size:clamp(36px,6.5vw,72px);font-weight:800;line-height:1.08;letter-spacing:-.04em;margin-bottom:20px}
.lp-grad{background:linear-gradient(135deg,var(--lp-accent) 0%,#a855f7 50%,#ec4899 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.lp-hero-sub{font-size:clamp(15px,2vw,18px);color:var(--lp-muted);max-width:580px;margin:0 auto 32px;line-height:1.65}
.lp-hero-actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-bottom:40px}

/* Trust bar */
.lp-trust{display:flex;gap:24px;justify-content:center;flex-wrap:wrap;margin-bottom:56px}
.lp-trust-item{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:500;color:var(--lp-muted)}
.lp-trust-item svg{color:var(--lp-green);flex-shrink:0}

/* Preview */
.lp-preview{max-width:940px;margin:0 auto;border-radius:16px;overflow:hidden;border:1px solid var(--lp-border);background:var(--lp-bg2);box-shadow:0 40px 120px rgba(0,0,0,.5),inset 0 1px rgba(255,255,255,.05)}
.lp-light .lp-preview{box-shadow:0 20px 60px rgba(0,0,0,.1)}
.lp-preview-chrome{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;border-bottom:1px solid var(--lp-border);background:var(--lp-card)}
.lp-dots{display:flex;gap:6px}.lp-dots span{width:10px;height:10px;border-radius:50%}.lp-dots span:nth-child(1){background:#ff5f57}.lp-dots span:nth-child(2){background:#febc2e}.lp-dots span:nth-child(3){background:#28c840}
.lp-preview-url{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--lp-dim);background:var(--lp-card);border:1px solid var(--lp-border);padding:4px 14px;border-radius:6px;font-weight:500}
.lp-preview-body{display:grid;grid-template-columns:200px 1fr}
.lp-preview-side{border-right:1px solid var(--lp-border);padding:14px;display:flex;flex-direction:column;gap:12px}
.lp-ps-user{display:flex;align-items:center;gap:8px}
.lp-ps-av{width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,var(--lp-accent),#a855f7);color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center}
.lp-ps-name{font-size:11px;font-weight:600}.lp-ps-status{font-size:9px;color:var(--lp-green);display:flex;align-items:center;gap:3px}
.lp-ps-status span{width:4px;height:4px;border-radius:50%;background:var(--lp-green)}
.lp-ps-menu{display:flex;flex-direction:column;gap:1px}.lp-ps-item{font-size:11px;padding:6px 10px;border-radius:6px;color:var(--lp-muted);font-weight:500}
.lp-ps-item.active{background:var(--lp-accent-glow);color:var(--lp-accent);font-weight:600}
.lp-preview-main{padding:14px;display:flex;flex-direction:column;gap:10px}
.lp-pm-topbar{display:flex;justify-content:space-between;align-items:center;padding:4px 0}
.lp-pm-greeting{font-size:13px;font-weight:600}.lp-pm-date{font-size:11px;color:var(--lp-dim)}
.lp-pm-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.lp-pm-stat{background:var(--lp-card);border:1px solid var(--lp-border);padding:10px;border-radius:8px}
.lp-pm-sl{font-size:8px;font-weight:600;color:var(--lp-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
.lp-pm-sv{font-size:16px;font-weight:800;font-family:var(--lp-display)}
.lp-pm-sc{font-size:9px;color:var(--lp-muted);margin-top:2px}
.lp-pm-chart{background:var(--lp-card);border:1px solid var(--lp-border);border-radius:8px;padding:12px;height:100px}
.lp-pm-chart-title{font-size:10px;font-weight:600;color:var(--lp-dim);margin-bottom:8px;text-transform:uppercase;letter-spacing:.04em}
.lp-pm-chart svg{width:100%;height:calc(100% - 20px)}.lp-chart-line{fill:none;stroke:var(--lp-accent);stroke-width:2;stroke-linecap:round;stroke-dasharray:1000;stroke-dashoffset:1000;animation:lpDraw 2.5s ease-out forwards}
@keyframes lpDraw{to{stroke-dashoffset:0}}

/* ── STATS BAR ────────────────────────────────────────────────────────────── */
.lp-stats-bar{padding:40px 0;border-top:1px solid var(--lp-border);border-bottom:1px solid var(--lp-border);background:var(--lp-bg2)}
.lp-stats-inner{display:flex;align-items:center;justify-content:center;gap:40px;flex-wrap:wrap}
.lp-stat-block{text-align:center}.lp-stat-num{font-family:var(--lp-display);font-size:32px;font-weight:800;letter-spacing:-.03em;color:var(--lp-text)}.lp-stat-label{font-size:12px;color:var(--lp-muted);margin-top:4px;font-weight:500}
.lp-stat-divider{width:1px;height:40px;background:var(--lp-border)}

/* ── SECTIONS ─────────────────────────────────────────────────────────────── */
.lp-section{padding:100px 0}.lp-section-alt{background:var(--lp-alt)}
.lp-sh{text-align:center;max-width:600px;margin:0 auto 56px}
.lp-overline{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.12em;color:var(--lp-accent);margin-bottom:12px;display:inline-block}
.lp-sh h2{font-family:var(--lp-display);font-size:clamp(26px,4vw,40px);font-weight:800;letter-spacing:-.03em;line-height:1.15;margin-bottom:14px}
.lp-sh p{font-size:15px;color:var(--lp-muted);line-height:1.6}

/* ── BENTO GRID ───────────────────────────────────────────────────────────── */
.lp-bento{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.lp-bento-card{background:var(--lp-card);border:1px solid var(--lp-border);border-radius:var(--lp-r);padding:32px 28px;transition:all .3s var(--lp-ease);text-align:left;overflow:hidden}
.lp-bento-card:hover{border-color:var(--lp-border-h);background:var(--lp-card-h);transform:translateY(-2px)}
.lp-bento-wide{grid-column:span 2}
.lp-bento-wide .lp-bc-content{max-width:50%}
.lp-bento-wide{display:flex;gap:24px;align-items:center;position:relative}
.lp-bc-icon{font-size:28px;margin-bottom:16px}
.lp-bento-card h3{font-family:var(--lp-display);font-size:17px;font-weight:700;margin-bottom:8px;letter-spacing:-.01em}
.lp-bento-card p{font-size:13px;color:var(--lp-muted);line-height:1.6}
.lp-bc-visual{margin-top:16px}
.lp-bento-wide .lp-bc-visual{margin-top:0;flex:1}

/* Feature visuals */
.lp-live-row{display:flex;align-items:center;gap:8px;padding:8px 12px;font-size:12px;font-weight:500;border-bottom:1px solid var(--lp-border)}
.lp-live-row:last-child{border-bottom:none}
.lp-live-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}.lp-live-dot.green{background:var(--lp-green);box-shadow:0 0 6px var(--lp-green)}.lp-live-dot.amber{background:var(--lp-amber)}.lp-live-dot.red{background:var(--lp-red)}
.lp-live-tag{margin-left:auto;font-size:10px;padding:2px 8px;border-radius:980px;background:rgba(52,211,153,.1);color:var(--lp-green);font-weight:600}
.lp-live-tag.warn{background:rgba(251,191,36,.1);color:var(--lp-amber)}.lp-live-tag.danger{background:rgba(248,113,113,.1);color:var(--lp-red)}
.lp-chat-bubble{padding:10px 14px;border-radius:12px;font-size:12px;line-height:1.5;margin-bottom:8px}
.lp-chat-bubble.user{background:var(--lp-accent);color:#fff;border-bottom-right-radius:4px;margin-left:20%}
.lp-chat-bubble.ai{background:var(--lp-card);border:1px solid var(--lp-border);border-bottom-left-radius:4px;margin-right:10%;color:var(--lp-text)}
.lp-anomaly-row{display:flex;align-items:center;gap:8px;padding:8px 0;font-size:12px;color:var(--lp-muted)}
.lp-a-badge{font-size:10px;padding:3px 8px;border-radius:6px;font-weight:600;flex-shrink:0}
.lp-a-badge.warn{background:rgba(251,191,36,.12);color:var(--lp-amber)}.lp-a-badge.danger{background:rgba(248,113,113,.12);color:var(--lp-red)}

/* ── TESTIMONIALS ─────────────────────────────────────────────────────────── */
.lp-testimonials{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.lp-testimonial-card{background:var(--lp-card);border:1px solid var(--lp-border);border-radius:var(--lp-r);padding:32px;text-align:left;transition:all .3s var(--lp-ease)}
.lp-testimonial-card:hover{border-color:var(--lp-border-h);transform:translateY(-2px)}
.lp-tc-stars{color:var(--lp-amber);font-size:14px;letter-spacing:2px;margin-bottom:16px}
.lp-testimonial-card p{font-size:14px;color:var(--lp-muted);line-height:1.65;margin-bottom:20px;font-style:italic}
.lp-tc-author{display:flex;align-items:center;gap:10px}
.lp-tc-av{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,var(--lp-accent),#a855f7);color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.lp-tc-name{font-size:13px;font-weight:600}.lp-tc-role{font-size:11px;color:var(--lp-dim)}

/* ── PRICING ──────────────────────────────────────────────────────────────── */
.lp-price-toggle{display:flex;align-items:center;justify-content:center;gap:14px;margin-bottom:48px}
.lp-price-toggle>span{font-size:14px;font-weight:500;color:var(--lp-dim);transition:color .2s}.lp-price-toggle>span.active{color:var(--lp-text)}
.lp-switch{width:44px;height:24px;border-radius:12px;padding:2px;background:var(--lp-card);border:1px solid var(--lp-border);cursor:pointer;position:relative;transition:background .3s}
.lp-switch.on{background:var(--lp-accent);border-color:var(--lp-accent)}
.lp-switch-thumb{width:18px;height:18px;border-radius:50%;background:#fff;display:block;transition:transform .3s var(--lp-ease);box-shadow:0 1px 3px rgba(0,0,0,.2)}
.lp-switch.on .lp-switch-thumb{transform:translateX(20px)}
.lp-save-pill{font-size:11px;font-weight:600;color:var(--lp-green);background:rgba(52,211,153,.1);padding:3px 10px;border-radius:980px;border:1px solid rgba(52,211,153,.2)}
.lp-pricing-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:980px;margin:0 auto}
.lp-price-card{background:var(--lp-bg);border:1px solid var(--lp-border);border-radius:var(--lp-r);padding:36px 28px;display:flex;flex-direction:column;text-align:left;transition:all .3s var(--lp-ease);position:relative}
.lp-price-card:hover{border-color:var(--lp-border-h);transform:translateY(-3px)}
.lp-price-card.featured{border-color:var(--lp-accent);box-shadow:0 0 0 1px var(--lp-accent),0 16px 48px var(--lp-accent-glow)}
.lp-pc-badge{position:absolute;top:-11px;left:50%;transform:translateX(-50%);background:var(--lp-accent);color:#fff;font-size:11px;font-weight:600;padding:4px 14px;border-radius:980px}
.lp-pc-tier{font-size:14px;font-weight:600;color:var(--lp-muted);margin-bottom:8px}
.lp-pc-price{font-family:var(--lp-display);font-size:40px;font-weight:800;letter-spacing:-.03em;margin-bottom:6px}
.lp-pc-price span{font-size:14px;font-weight:500;color:var(--lp-dim);margin-left:2px}
.lp-pc-desc{font-size:13px;color:var(--lp-muted);margin-bottom:24px;line-height:1.5}
.lp-price-card ul{list-style:none;display:flex;flex-direction:column;gap:10px;margin-bottom:28px;flex-grow:1}
.lp-price-card li{font-size:13px;color:var(--lp-muted);display:flex;align-items:center;gap:8px}
.lp-price-card li::before{content:'✓';color:var(--lp-accent);font-weight:700;font-size:12px}

/* ── TUTORIAL ─────────────────────────────────────────────────────────────── */
.lp-tut-grid{display:grid;grid-template-columns:300px 1fr;gap:28px}
.lp-tut-tabs{display:flex;flex-direction:column;gap:8px}
.lp-tut-tab{display:flex;align-items:center;gap:14px;padding:16px;border-radius:var(--lp-rs);background:transparent;border:1px solid var(--lp-border);cursor:pointer;text-align:left;font-family:var(--lp-font);color:var(--lp-text);transition:all .25s var(--lp-ease);position:relative;overflow:hidden}
.lp-tut-tab:hover{background:var(--lp-card)}.lp-tut-tab.active{border-color:var(--lp-accent);background:var(--lp-accent-glow)}
.lp-tut-num{width:30px;height:30px;border-radius:50%;background:var(--lp-card);border:1px solid var(--lp-border);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:var(--lp-muted);flex-shrink:0;transition:all .25s}
.lp-tut-tab.active .lp-tut-num{background:var(--lp-accent);border-color:var(--lp-accent);color:#fff}
.lp-tut-title{font-size:13px;font-weight:600}.lp-tut-sub{font-size:11px;color:var(--lp-dim);margin-top:1px}
.lp-tut-progress{position:absolute;bottom:0;left:0;right:0;height:2px;background:var(--lp-border)}.lp-tut-progress-fill{height:100%;background:var(--lp-accent);animation:lpProgress 5s linear forwards}
@keyframes lpProgress{from{width:0}to{width:100%}}
.lp-tut-content{background:var(--lp-card);border:1px solid var(--lp-border);border-radius:var(--lp-r);padding:36px;min-height:400px;display:flex;flex-direction:column;justify-content:center;text-align:left}
.lp-tut-fade{animation:lpFade .4s var(--lp-ease)}
@keyframes lpFade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.lp-tut-content h3{font-family:var(--lp-display);font-size:20px;font-weight:700;margin-bottom:10px;letter-spacing:-.02em}
.lp-tut-content p{font-size:14px;color:var(--lp-muted);line-height:1.65;margin-bottom:14px}
.lp-tut-highlight{background:var(--lp-accent-glow);border:1px solid rgba(41,151,255,.15);border-radius:var(--lp-rs);padding:14px 18px;font-size:13px;color:var(--lp-muted);line-height:1.5;margin-bottom:12px}
.lp-tut-highlight strong{color:var(--lp-text)}
.lp-tut-mockup{display:flex;flex-direction:column;gap:8px;margin-top:12px}
.lp-tm-field{display:flex;align-items:center;gap:12px;padding:8px 12px;background:var(--lp-card);border:1px solid var(--lp-border);border-radius:6px;font-size:12px}
.lp-tm-field span{color:var(--lp-dim);font-weight:500;min-width:90px}.lp-tm-field div{font-weight:600;color:var(--lp-text)}
.lp-tm-locked{color:var(--lp-accent)!important;font-size:11px}
.lp-code-block{border-radius:var(--lp-rs);overflow:hidden;margin-top:8px;border:1px solid var(--lp-border)}
.lp-code-head{display:flex;justify-content:space-between;padding:8px 14px;background:var(--lp-card);font-size:11px;color:var(--lp-dim);font-weight:600;border-bottom:1px solid var(--lp-border)}
.lp-code-copy{font-family:'JetBrains Mono',monospace;font-weight:500}
.lp-code-block pre{background:var(--lp-code);margin:0;padding:14px;font-size:12px;line-height:1.6;overflow-x:auto;color:var(--lp-green);font-family:'JetBrains Mono','Fira Code',monospace}
.lp-invite-card{background:var(--lp-card);border:1px solid var(--lp-border);border-radius:var(--lp-rs);padding:20px;margin-top:8px}
.lp-invite-label{font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:var(--lp-dim);font-weight:600;margin-bottom:6px}
.lp-invite-code{font-size:28px;font-weight:800;color:var(--lp-accent);font-family:'JetBrains Mono',monospace;letter-spacing:.08em;margin-bottom:14px}
.lp-invite-steps{display:flex;flex-direction:column;gap:6px}
.lp-invite-step{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--lp-muted)}
.lp-invite-step span{width:20px;height:20px;border-radius:50%;background:var(--lp-accent-glow);color:var(--lp-accent);font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.lp-invite-step code{background:var(--lp-card-h);padding:1px 6px;border-radius:4px;font-size:11px}

/* ── FAQ ──────────────────────────────────────────────────────────────────── */
.lp-faq-list{max-width:720px;margin:0 auto;display:flex;flex-direction:column;gap:8px}
.lp-faq-item{border:1px solid var(--lp-border);border-radius:var(--lp-rs);overflow:hidden;transition:border-color .25s}
.lp-faq-item:hover{border-color:var(--lp-border-h)}.lp-faq-item.open{border-color:var(--lp-accent)}
.lp-faq-q{width:100%;padding:18px 20px;background:transparent;border:none;color:var(--lp-text);font-size:14px;font-weight:600;font-family:var(--lp-font);cursor:pointer;display:flex;align-items:center;justify-content:space-between;text-align:left}
.lp-faq-chev{color:var(--lp-dim);transition:transform .3s var(--lp-ease);flex-shrink:0}
.lp-faq-item.open .lp-faq-chev{transform:rotate(180deg);color:var(--lp-accent)}
.lp-faq-a{overflow:hidden;padding:0 20px;font-size:14px;color:var(--lp-muted);line-height:1.65;transition:max-height .35s var(--lp-ease),padding-bottom .35s var(--lp-ease)}

/* ── CTA ──────────────────────────────────────────────────────────────────── */
.lp-cta{text-align:center;padding:100px 0;position:relative;overflow:hidden}
.lp-cta-bg{position:absolute;bottom:-100px;left:50%;transform:translateX(-50%);width:800px;height:400px;background:radial-gradient(ellipse,var(--lp-accent-glow) 0%,transparent 65%);pointer-events:none}
.lp-cta-inner{position:relative;z-index:1}
.lp-cta h2{font-family:var(--lp-display);font-size:clamp(28px,5vw,44px);font-weight:800;letter-spacing:-.03em;margin-bottom:16px}
.lp-cta p{font-size:16px;color:var(--lp-muted);max-width:500px;margin:0 auto 28px}
.lp-cta-note{font-size:12px;color:var(--lp-dim);margin-top:20px}

/* ── FOOTER ───────────────────────────────────────────────────────────────── */
.lp-footer{border-top:1px solid var(--lp-border);padding:60px 0 40px;background:var(--lp-bg)}
.lp-footer-inner{display:flex;flex-direction:column;gap:40px}
.lp-footer-top{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:40px}
.lp-footer-brand p{font-size:13px;color:var(--lp-dim);line-height:1.6;max-width:260px}
.lp-footer-col{display:flex;flex-direction:column;gap:8px}
.lp-footer-col h4{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--lp-muted);margin-bottom:4px}
.lp-footer-col a{font-size:13px;color:var(--lp-dim);text-decoration:none;transition:color .2s}
.lp-footer-col a:hover{color:var(--lp-text)}
.lp-footer-bottom{border-top:1px solid var(--lp-border);padding-top:24px}
.lp-footer-bottom p{font-size:12px;color:var(--lp-dim);text-align:center}

/* ── RESPONSIVE ───────────────────────────────────────────────────────────── */
@media(max-width:900px){.lp-bento{grid-template-columns:1fr 1fr}.lp-bento-wide{grid-column:span 2;flex-direction:column}.lp-bento-wide .lp-bc-content{max-width:100%}.lp-pricing-grid,.lp-testimonials{grid-template-columns:1fr;max-width:420px;margin:0 auto}.lp-tut-grid{grid-template-columns:1fr}.lp-footer-top{grid-template-columns:1fr 1fr;gap:24px}.lp-pm-stats{grid-template-columns:repeat(2,1fr)}}
@media(max-width:768px){.lp-nav-links,.lp-nav-right{display:none}.lp-burger{display:flex}.lp-preview-body{grid-template-columns:1fr}.lp-preview-side{border-right:none;border-bottom:1px solid var(--lp-border)}.lp-bento{grid-template-columns:1fr}.lp-bento-wide{grid-column:span 1}.lp-stats-inner{gap:24px}.lp-stat-divider{display:none}.lp-hero{padding:100px 0 40px}.lp-section{padding:72px 0}.lp-footer-top{grid-template-columns:1fr}.lp-trust{gap:16px}}
@media(max-width:480px){.lp-hero h1{font-size:32px}.lp-tut-content{padding:24px}.lp-btn-lg{padding:11px 22px;font-size:14px}}
`;
