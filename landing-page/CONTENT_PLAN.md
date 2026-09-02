# Recovery Router - Landing Page Content Plan

> Razorpay AI Buildathon 2026 - Track 3: AI Revenue Recovery
> Built by Albert Abishek I

---

## Winning Patterns Extracted from 4 Previous Internship Landing Pages

### What all 4 winners share:
1. **Hero**: Badge/label → Big headline → Subtitle → 2-3 CTAs (Live Demo + GitHub + API Docs)
2. **Numbered sections** (01, 02, 03...) with sticky nav - lets judges jump around
3. **Dark theme** with accent gradients - all 4 use dark backgrounds
4. **Problem first** - explain the gap/pain before the solution
5. **Pipeline/architecture visualization** - numbered step flow, not just text
6. **Real outputs & proof** - screenshots, metrics, actual execution data
7. **Honest limitations** - edge cases, what's not done - builds trust with technical judges
8. **Journey/war stories** - the debugging narrative, pivots, what broke
9. **About the Developer** - education, experience, skills, projects (Page 2 did this best)
10. **Downloads/assets** - resume, source code, workflow files
11. **Video demo** with timestamp breakdown
12. **Tech stack strip** - visual badges of technologies used
13. **Future roadmap** - what you'd build next
14. **Sticky nav** with section anchors

### What Page 1 (Funnel Truffle) did best - and why user called it "best order and contents":
- Clean numbered section progression that tells a story
- "Why I chose this problem" section - shows intentionality
- "The clarifying question I asked" - shows depth of thinking
- Real execution outputs with category tabs (Sheets, Emails, Slack)
- "Production Thinking" section with numbered honest edge cases
- Each edge case: what happened, why, what the fix would be
- Assignment question answer embedded in the page
- Downloadable assets section

### What Page 2 did best - About the Developer:
- Photo/avatar area, name, location
- Education with institution, degree, semester
- Work experience entries with company, role, dates, description
- Notable projects with dates and descriptions
- Technical skills organized by category (Languages, Frameworks, AI & Automation)

---

## Landing Page Structure - Section by Section

### STICKY NAV (always visible)
```
Recovery Router    |  Problem  |  Solution  |  Architecture  |  How It Works  |  War Stories  |  Impact  |  Demo  |  About  |  Links
```

---

### SECTION 0: HERO
**Goal:** Hook in 3 seconds. Show what this is, who built it, and give immediate access.

**Layout:**
- Top badge: `RAZORPAY AI BUILDATHON 2026 · TRACK 3 · REVENUE RECOVERY`
- Main headline: **"What happens after a payment fails?"**
- Animated text ticker below headline (scrolling left): `UPI timed out... Card declined... Cart abandoned... Invoice overdue... Insufficient funds... Gateway error... Bank downtime...`
- Tagline: **"Vulcan routes payments. Recovery Router routes failures."**
- One-liner paragraph: "An AI-powered engine that classifies every revenue leak - payment failures, cart abandonment, overdue invoices - routes each to the optimal recovery action, and executes through the right channel at the right time. With honest metrics that never inflate results."
- 3 CTA buttons:
  - **Live Dashboard** → app.albertabishek.com (primary, filled)
  - **API Docs** → api.albertabishek.com/docs (outline)
  - **GitHub** → github.com/albertabishek/Recovery-Router- (outline)
- Right side / below: Floating stat cards (like Page 1):
  - "12 FAILURE CATEGORIES" 
  - "3+1 AI MODELS"
  - "114 AUTOMATED TESTS"
  - "3 REVENUE LEAK TYPES"

**Visual:** Dark background, gradient accent on headline keywords, floating stat cards with subtle glow

---

### SECTION 1: THE PROBLEM - Why This Track Exists
**Section label:** `01 - THE PROBLEM`
**Goal:** Make judges feel the scale of revenue leakage. Data-driven, sourced.

**Sub-section 1a: The Scale**
Stat cards row (big numbers with sources):
| Stat | Number | Source |
|------|--------|--------|
| D2C payment success rate in India | 68–74% | Razorpay, May 2026 |
| Customers who won't return after decline | 40% | Razorpay, May 2026 |
| Cart abandonment caused by payment failures | 70% | Razorpay, May 2026 |
| Automated retry recovery rate | Only 15–20% | Razorpay, May 2026 |
| Global cost of failed payments | $118.5B+ annually | LexisNexis/Accuity |
| Industry median recovery rate | 47.6% | Digital Applied |
| Best-in-class recovery programs | 70–85% | Digital Applied |

**Sub-section 1b: What Exists Today - And the Gap**
Two-column layout:
- Left: "What Razorpay Built" - Vulcan (before payment), Agent Studio (individual agents), Failed Payment Recovery (notification system)
- Right: "What's Missing" - No unified classify-route-act-measure pipeline across all 3 leak types

**Key visual:** Payment lifecycle diagram
```
BEFORE PAYMENT        DURING PAYMENT        AFTER FAILURE
Magic Checkout   →    Vulcan (Routing)   →    ???
                                                ↓
                                          Recovery Router
```

**Sub-section 1c: How the World Handles It (Competitor Snapshot)**
Compact table - 6 key competitors, what they do, their limitation:
| Competitor | Approach | Limitation |
|-----------|----------|------------|
| Stripe | Smart Retries + card updates (55% recovery) | Email-only dunning, retry and dunning independent |
| Adyen | Contextual multi-armed bandits for retry timing | Retry-only, no customer communication |
| Cashfree | "Relay" AI agent for failed payments + carts | Direct competitor, but single-agent not pipeline |
| Recurly | Intelligent Dunning ML (70-80% recovery) | Subscriptions only |
| Chargebee | Pre-dunning workflows (30-40% + 15-22%) | Subscriptions only |
| Most others | Fixed retry schedules, email-only | No multi-channel, no classification |

**Closing line:** "Everyone focuses on retry mechanics. Nobody combines diagnostic intelligence with personalized multi-channel recovery across all three leak types in a single engine."

---

### SECTION 2: MY THINKING - Why I Built It This Way
**Section label:** `02 - MY THINKING`
**Goal:** Show intentionality. This isn't a random hackathon project - every decision was deliberate.

5 principle cards (icon + title + 1-2 line explanation):

1. **"Without ROI, there will be no features"**
   Rejected features that look impressive but don't improve recovery. No Promise-to-Pay, no complex ML that can't be explained, no vanity metrics.

2. **"Think Like You Already Work There"**
   Cloned Razorpay's actual UI - design tokens, SVG icons, color system. When judges look at the dashboard, it feels native.

3. **"Honest Metrics Over Impressive Numbers"**
   Ghost recovery prevention: if no outreach was sent, it's `organic_recovery`, not `recovered`. Tracks "sent" not "delivered" because delivery receipts aren't built yet.

4. **"Safety First - It's Financial Software"**
   HMAC-SHA256 webhooks, XSS prevention, AI input sanitization, distributed locks, 3-layer give-up prevention, database-level trigger as last line of defense.

5. **"Real Architecture, Not Demo Architecture"**
   `acks_late=True`, `reject_on_worker_lost=True`, exponential backoff, distributed locks, conditional DB updates. If a Razorpay engineer reviewed this, they'd see production patterns.

---

### SECTION 3: THE SOLUTION - What Recovery Router Does
**Section label:** `03 - THE SOLUTION`
**Goal:** Clearly explain the product in a scannable format.

**Sub-section 3a: One Engine, Three Leak Types**
3-column cards:
| Payment Failures | Cart Abandonment | Overdue Invoices |
|-----------------|------------------|-----------------|
| Razorpay `payment.failed` webhook | Merchant POST via API | Invoice scanner polls every 6h |
| 12 failure categories | Classified by intent | Classified by days overdue |
| Immediate to 4h delay | 1h strategic delay | Immediate to 24h |

**Sub-section 3b: The Pipeline - Classify → Route → Act → Measure**
4-step numbered pipeline (visual, like Page 1's architecture):

**Step 1: CLASSIFY (AI)**
- 3-model fallback chain: Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini
- Rule-based fallback if all AI fails (system never blocks on AI)
- 12 categories with recovery probability estimates

**Step 2: ROUTE (Dynamic Budgets)**
- `max_attempts` computed per event - not fixed for everyone
- High-value UPI timeout → 5 attempts
- Browse-only cart → 0 attempts (no ROI)
- User-cancelled → 2 attempts (respect the signal)

**Step 3: ACT (Multi-Channel)**
- WhatsApp: Green API → Twilio → Email fallback
- SMS: Twilio → WhatsApp → Email fallback  
- Email: Resend with AI-personalized HTML
- Every provider attempt logged in `degradation_path`

**Step 4: MEASURE (Honest Metrics)**
- 4-strategy reconciliation matching
- Ghost recovery prevention (organic ≠ recovered)
- Double-attribution prevention
- Currency match, amount tolerance (1%)

**Sub-section 3c: 12 Failure Categories Table**
Full table with: Category | Recovery Probability | Channel | Timing | Max Attempts
(from README - all 12 categories)

---

### SECTION 4: ARCHITECTURE
**Section label:** `04 - ARCHITECTURE`
**Goal:** Show the technical depth. For technical judges.

**Sub-section 4a: System Architecture Diagram**
ASCII/visual diagram showing all 6 components:
FastAPI → Celery + Redis → Pipeline (Classify→Route→Link→Message→Send→Log)
+ Escalation Engine (5min) + Invoice Scanner (6h)
+ Provider fallback chains (WhatsApp/SMS/Email)

**Sub-section 4b: Tech Stack Grid**
Visual badges/cards (like Page 1's "BUILT WITH" strip):

| Component | Technology | Why |
|-----------|-----------|-----|
| API | FastAPI | Async, auto-docs, Pydantic validation |
| Task Queue | Celery + Redis | Late ACK, crash recovery, periodic scheduling |
| Database | Supabase (PostgreSQL) | Realtime subscriptions, RLS |
| AI Gateway | OpenRouter | Multi-model, no vendor lock-in |
| AI Models | Claude Haiku → Gemini Flash → GPT-4o-mini | Speed-first fallback chain |
| Payments | Razorpay Orders API | Unlimited (vs 30-link limit) |
| WhatsApp | Green API + Twilio | Personalized text + template fallback |
| SMS | Twilio | Industry standard |
| Email | Resend | AI-personalized HTML |
| Frontend | React 19 + Vite 8 + Tailwind 4 | Fast HMR, Razorpay UI clone |
| Realtime | Supabase Realtime | WebSocket live updates |
| Cache/Locks | Redis | 6 roles: broker, cache, dedup, rate limit, locks, PII store |

**Sub-section 4c: Security Architecture**
Compact table of 11 defense layers (from security.md):
Webhook HMAC → Body size limits → Dedup → Rate limiting → AI sanitization → XSS prevention → PII protection → Race condition locks → 3-layer give-up prevention → DB trigger → CORS

**Sub-section 4d: Escalation Engine**
Visual flow:
- Every 5 minutes via Celery Beat
- AI analyzes attempt history → decides next channel + tone
- 3-layer safety prevents premature give-up
- Quiet hours (9 PM – 9 AM IST)
- Category-specific retry delays (1h to 48h)
- Channel rotation: WhatsApp → Email → SMS → Email

---

### SECTION 5: THE JOURNEY - From Prototype to Production
**Section label:** `05 - THE JOURNEY`
**Goal:** Show the process. Judges love seeing how you think, not just what you built.

**Timeline cards** (like Page 4's phased journey):

**Phase 1: Research (Before Aug 28)**
- Studied Razorpay's full product ecosystem: Vulcan, Agent Studio, Magic Checkout
- Analyzed 13 competitors globally
- Researched 25 Track 3 entries, 12 public repos
- Core insight: "Vulcan routes payments. Recovery Router routes failures."

**Phase 2: n8n Prototype**
- 5 workflows proving the classify-route-act-measure logic
- Proved the pipeline worked, but n8n lacked distributed locking, dedup, race condition handling
- These prototypes would later come back as the Ghost Writer bug

**Phase 3: Full Rebuild (Aug 28)**
- First commit: 4:06 PM IST - full 6-component architecture from day one
- "Everything will be async. Use Celery, workers, everything - no tricks."

**Phase 4: Hardening (Aug 30)**
- 8:37 AM - Security hardening, auth, AI improvements
- 8:47 AM - Premature Give-Up bug → 3-layer defense
- 10:59 AM - Ghost recovery prevention, honest metrics
- 12:57 PM - TOCTOU race condition → distributed locks
- 5:42 PM - Ghost Writer bug discovered → database trigger
- 5:45-5:50 PM - 3 Railway build failures in 8 minutes

**Phase 5: Final Polish (Aug 31)**
- 7:34 AM - Security audit: P0/P1 fixes
- System ready for submission

---

### SECTION 6: WAR STORIES - What Broke & How I Fixed It
**Section label:** `06 - WAR STORIES`
**Goal:** The honest edge cases section. Like Page 1's "Production Thinking" - this is what separates winners.

**7 bug cards** - each with: Severity badge, What Happened, Root Cause, Fix, Lesson

1. **The Premature Give-Up** (P0)
   Events exhausted after 1 attempt instead of 5. Schema default "give_up" → 3-layer defense.

2. **The TOCTOU Race Condition** (P0)
   Two Celery tasks processing same event concurrently. → Distributed locks + conditional updates + fresh re-read.

3. **The Ghost Writer Mystery** ⭐ (P0 - Star Story)
   Event #18 in impossible state. Old n8n workflows still writing to DB behind the backend's back. → Unpublished workflows + PostgreSQL trigger as database-level defense.

4. **Railway Build Failures** (P1)
   3 attempts in 8 minutes. Nixpacks fighting. → Let the platform auto-detect.

5. **WhatsApp Personalization** (P1)
   Twilio requires templates, can't send custom text. → Green API primary, Twilio as fallback.

6. **Dynamic Budget Discovery** (P1)
   Every event showing 1/5 attempts. → Dynamic `compute_max_attempts()` based on amount, probability, category.

7. **Security Audit** (P0/P1)
   6 security issues found and fixed in one commit.

---

### SECTION 7: IMPACT & ROI
**Section label:** `07 - IMPACT`
**Goal:** Show business value. For non-technical judges.

**Sub-section 7a: What the System Demonstrates**
Before/After comparison table:
| Metric | Without Recovery Router | With Recovery Router |
|--------|----------------------|---------------------|
| Failed payment response | Manual follow-up or nothing | AI-classified, multi-channel, automated in seconds |
| Cart recovery | No automated recovery | High-intent only - browse-only gets 0 attempts |
| Invoice collection | Manual, takes weeks | Automated within hours, tone matches urgency |
| Customer re-engagement | 40% won't return | Multi-channel within optimal timing window |
| Cost efficiency | Same effort on every failure | Dynamic budgets - zero spend on unrecoverable |

**Sub-section 7b: Cost Efficiency**
- ~$0.008 per recovery attempt (AI classification cost)
- Break-even: 0.5% recovery rate (industry median: 47.6%)
- Zero-attempt events (fraud, browse-only) = zero cost
- Per-resource cooldowns prevent spam and wasted spend

**Sub-section 7c: What a Razorpay PM Would See**
Bullet points:
- Organic vs outreach-driven recovery clearly separated
- Channel effectiveness ranking backed by data
- Failure category distribution across merchant base
- Full audit trail - every AI decision, provider attempt, state change logged

**Caveat box:** "All metrics are from test-mode data with simulated scenarios. The system tracks provider acceptance ('sent'), not delivery receipts. Production recovery rates depend on merchant volume, payment mix, and customer demographics."

---

### SECTION 8: DEMO
**Section label:** `08 - DEMO`
**Goal:** The video and live links.

**Video embed** (or thumbnail + play link) - 5-minute demo

**Timestamp breakdown** (like Page 4):
| Time | What's Shown |
|------|-------------|
| 0:00–0:15 | Problem - Razorpay's D2C success rates, the recovery gap |
| 0:15–0:30 | Thesis - one pipeline for three leak types |
| 0:30–2:30 | Live Payment Demo - real Razorpay test-mode checkout → webhook → full pipeline |
| 2:30–3:10 | Simulated Cart Abandonment - different classification, budget, tone |
| 3:10–3:40 | Honest tracking - organic vs outreach-driven, provider acceptance |
| 3:40–4:05 | Safety proofs - dedup, escalation, 3-layer give-up prevention |
| 4:05–4:25 | Ghost Writer bug - the star war story |
| 4:25–5:00 | Limitations, open items, close |

---

### SECTION 9: SCREENSHOTS
**Section label:** `09 - SCREENSHOTS`
**Goal:** Visual proof. Judges need to see it works.

Gallery with tabs (like Page 1's output gallery):
- **Dashboard Overview** - hero card, stat tiles, channel performance, live feed
- **Recovery Events** - event list with status tabs, detail panel with pipeline visualization
- **Analytics** - KPI strip, channel ranking, failure categories
- **Simulator** - 10 scenarios, Try Live Payment with Razorpay checkout
- **Audit Logs** - full attempt trail with AI reasoning, degradation paths
- **Self-Hosted Checkout** - Razorpay modal, recovery_router provenance
- **Health Monitoring** - component status badges

---

### SECTION 10: TESTING
**Section label:** `10 - TESTING`
**Goal:** Show production-grade verification. 114 tests is unusual for a buildathon.

**Stat strip:**
- 114 test functions across 6 files
- 0 mocks - all integration tests against live system
- 20 security tests (SQL injection, XSS, CORS, path traversal)
- 10 parametrized pipeline scenarios
- 6 load/concurrency tests

**Test categories** (compact cards):
- API Endpoints (38 tests)
- Pipeline Classification (15 tests) 
- Security (20 tests)
- Error Handling (13 tests)
- Load & Concurrency (6 tests)
- E2E Standalone (31 tests)

**Key insight line:** "No mocks. All tests run against the live server with real Redis, real Supabase, real AI classification. Tests verify actual production behavior, not mocked approximations."

---

### SECTION 11: KNOWN LIMITATIONS
**Section label:** `11 - HONEST GAPS`
**Goal:** Like Page 1's "Production Thinking" - honest about what's not done. This builds massive trust.

Numbered limitation cards (similar to Page 1's edge cases format):

1. **Test-mode only** - All Razorpay operations use test-mode keys. No production merchant data.
2. **Tracks "sent" not "delivered"** - Provider acceptance ≠ customer receipt. Delivery receipts not integrated yet.
3. **Shared password auth** - Dashboard uses single password, not per-user JWT. Fine for demo, not production.
4. **Service key in backend** - Supabase service key bypasses RLS. Production would use scoped tokens.
5. **CORS allows all** - `*` origin in some configs. Production needs explicit allowlist.
6. **Single Celery worker** - Handles current load but would bottleneck at scale.
7. **Amount tolerance edge cases** - 1% tolerance could false-match on small amounts.
8. **Quiet hours assume IST** - No per-customer timezone support yet.

**Closing line:** "These are documented because honesty about what's unfinished matters more than pretending everything is done."

---

### SECTION 12: WHERE IT FITS - Razorpay Product Analysis
**Section label:** `12 - RAZORPAY FIT`
**Goal:** Show judges this isn't a standalone toy - it completes Razorpay's ecosystem.

**Payment Lifecycle Diagram:**
```
BEFORE              DURING              AFTER
Magic Checkout  →   Vulcan (AI)    →   Recovery Router
(UX optimization)   (Smart routing)    (Classify-Route-Act-Measure)
```

**Product Synergy Table** (compact):
| Razorpay Product | How Recovery Router Integrates |
|-----------------|------------------------------|
| Vulcan | Handles what Vulcan can't prevent |
| Agent Studio | Could dispatch to Agent Studio agents |
| Payment Gateway | Consumes its failure webhooks |
| Magic Checkout | Checkout data improves channel selection |
| Subscriptions | Adds intelligence beyond T+1/T+2/T+3 retry |

**Positioning line:** "Recovery Router doesn't replace any Razorpay product. It's the brain that connects them."

---

### SECTION 13: ABOUT THE DEVELOPER
**Section label:** `13 - ABOUT ME`
**Goal:** Personal section. Follow Page 2's format - the best "About" section.

**Layout:** Photo/avatar + info cards

**Info:**
- **Name:** Albert Abishek I
- **Location:** Vellore, Tamil Nadu
- **Education:** B.E. Computer Science Engineering (2023–2027), Thanthai Periyar Govt. Institute of Technology, Current: 5th Semester
- **Portfolio link**

**Work Experience** (cards with company, role, dates):
- [Fill in actual experience]

**Notable Projects** (cards with name, date, description):
- Recovery Router (current)
- [Other projects]

**Technical Skills** (organized by category like Page 2):
- Languages: Python, JavaScript, TypeScript, C++, SQL, HTML/CSS
- Frameworks: FastAPI, React, Next.js, Flask, Django, Node.js, Tailwind
- AI & ML: OpenRouter, LangChain, OpenAI API
- Automation: n8n, Celery, Redis
- Infrastructure: Railway, Vercel, Supabase, Docker
- Payments: Razorpay API, Stripe

**"Why I Built It This Way" quote:**
"I didn't build a hackathon project. I built what I would build if I were a Razorpay engineer assigned to solve this problem on Day 1."

---

### SECTION 14: ANTICIPATED QUESTIONS
**Section label:** `14 - FAQ`
**Goal:** Preemptively answer judge questions. Shows depth of thinking.

6-7 accordion/expandable Q&A:
1. How is this different from Razorpay's existing Failed Payment Recovery?
2. Why not use Razorpay Agent Studio?
3. What's the actual recovery rate?
4. How do you handle scale?
5. What about customer consent and spam?
6. Why three AI models instead of one?
7. What would you build next?

(Answers from landing.md - already written)

---

### SECTION 15: LINKS & DOWNLOADS
**Section label:** `15 - RESOURCES`
**Goal:** Everything in one place. Like Page 1's downloads section.

**Link cards:**
- Live Dashboard → app.albertabishek.com
- API Documentation → api.albertabishek.com/docs
- GitHub Repository → github.com/albertabishek/Recovery-Router-
- API Health Check → api.albertabishek.com/api/health
- Resume (PDF download)

---

### SECTION 16: FOOTER
**Simple closing:**
- "Recovery Router - Razorpay AI Buildathon 2026, Track 3"
- "Built by Albert Abishek I"
- Links: LinkedIn | GitHub | Portfolio
- Copyright line

---

## Design Notes

### Visual Style
- **Dark theme** (all 4 winners use dark) - keep the current `--bg-deep: #0a0a0f` palette
- **Accent colors:** Razorpay blue (#3395FF) as primary accent alongside the existing purple/cyan gradients
- **Typography:** Inter (body) + JetBrains Mono (code/stats) - already in current page
- **Animations:** Subtle - floating orbs (keep), scroll-triggered fade-ins, typewriter on hero
- **Cards:** Dark glass-morphism cards with subtle border glow

### Layout Principles
- Max width 1200px, centered
- Numbered sections (01, 02, 03...) - consistent with winning pattern
- Each section has a label badge + headline + content
- Tables use the compact dark style from current page
- Sticky nav with scroll-spy highlighting

### Mobile
- Hamburger nav on mobile
- Stack columns vertically
- Tables scroll horizontally
- Stat cards stack 2-per-row then 1-per-row

### Screenshots
- Need to capture actual screenshots of the running dashboard for Section 9
- Each screenshot gets a caption describing what it shows

### Content Priority
For judges scanning quickly, the most important sections in order:
1. Hero (3-second hook)
2. The Problem (why this matters)
3. The Solution (what it does)
4. War Stories (shows real engineering)
5. Demo video
6. Architecture (for technical judges)
7. About Me (for hiring decision)
