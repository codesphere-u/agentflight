(() => {
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  const INSTALL_MODES = {
    pypi: {
      caption: "pip install agentflight-mcp",
      command: "pip install agentflight-mcp && agentflight doctor",
    },
    uvx: {
      caption: "uvx --from agentflight-mcp agentflight doctor",
      command: "uvx --from agentflight-mcp agentflight serve-mcp",
    },
    mcp: {
      caption: "claude mcp add --transport http agentflight https://agentflight-tau.vercel.app/mcp",
      command: "claude mcp add --transport http agentflight https://agentflight-tau.vercel.app/mcp",
    },
    pytest: {
      caption: "pytest --flight-mode=replay",
      command: "pytest -v --flight-mode=replay",
    },
  };

  const HOME_PREVIEWS = {
    term: `$ agentflight demo

FlightRecorder: 4 spans chained (SHA-256 verified, API keys scrubbed)
CassetteReplayer: replayed 4/4 spans in 0.011 ms  [$0.0000 CI spend]
TrajectoryCircuitBreaker: tripped ping_pong_oscillation (A -> B -> A -> B)
ToolSmellLinter: 200 MCP schemas audited in 119.3 ms (1,676 tools/sec)`,
    cassette: JSON.stringify(
      {
        schema_version: "1.5.0",
        agent_id: "sre-incident-responder",
        genesis_hash: "0000000000000000000000000000000000000000000000000000000000000000",
        spans: [
          {
            step_index: 0,
            kind: "llm_turn",
            actor: "planner_model",
            input_payload: { api_key: "[REDACTED_SECRET]", goal: "Check payment-api p99 latency" },
            cost_usd: 0.0021,
            step_hash: "8f3c9b71d0e4...c92a",
          },
          {
            step_index: 1,
            kind: "mcp_rpc",
            actor: "prometheus.query_metrics",
            input_payload: { service: "payment-api", window: "15m" },
            output_payload: { p99_latency_ms: 1840.0, anomaly: true },
            prev_hash: "8f3c9b71d0e4...c92a",
            step_hash: "3b19a4c2f811...e41f",
          },
        ],
      },
      null,
      2
    ),
    linter: JSON.stringify(
      {
        ergonomics_score: 64,
        grade: "D",
        findings: [
          {
            rule_id: "TS001",
            severity: "error",
            tool_name: "doStuff",
            message: "Description shorter than 15 chars leaves model routing ambiguous.",
          },
          {
            rule_id: "TS010",
            severity: "error",
            tool_name: "delete_customer",
            message: "Destructive tool lacks confirm/dry_run/idempotency_key safety parameter.",
          },
        ],
      },
      null,
      2
    ),
  };

  const DOC_INSTALL_PRESETS = {
    pypi: {
      eyebrow: "INSTALL PYTHON SDK & CLI",
      note: "Requires Python 3.10+. Core recording, replay, redaction, circuit breaking, and linting modules have zero runtime dependencies.",
      code: "pip install agentflight-mcp && agentflight doctor",
    },
    claude: {
      eyebrow: "CONNECT TO CLAUDE CODE CLI",
      note: "Connect directly to the stateless Vercel Streamable HTTP endpoint or add stdio mode with uvx.",
      code: "claude mcp add --transport http agentflight https://agentflight-tau.vercel.app/mcp",
    },
    cursor: {
      eyebrow: "LOCAL STDIO MCP SERVER (CURSOR / CLAUDE DESKTOP)",
      note: "Run agentflight serve-mcp locally when tools inspect local .flight.json cassettes on disk.",
      code: 'uvx --from agentflight-mcp agentflight serve-mcp',
    },
    ci: {
      eyebrow: "GITHUB ACTIONS PRE-FLIGHT CI GATE",
      note: "Audit MCP schemas and block cost or loop regressions in pull requests cleanly.",
      code: "agentflight ci --schema-file tools.json --cassette tests/cassettes/run.flight.json --fail-on-smell --github-summary",
    },
  };

  const LINTER_PRESETS = {
    flawed: [
      {
        name: "search_records",
        description: "Find",
        inputSchema: {
          type: "object",
          properties: {
            mode: { type: "boolean" },
            status: { type: "string" },
          },
        },
      },
      {
        name: "find_records",
        description: "Search user records by query",
        inputSchema: {
          type: "object",
          properties: {
            query: { type: "string" },
          },
        },
      },
    ],
    hardened: [
      {
        name: "lookup_user",
        description: "Look up verified customer profile by exact user ID or email. Read-only database query.",
        inputSchema: {
          type: "object",
          properties: {
            user_id: {
              type: "string",
              description: "Unique customer UUID identifier.",
            },
            include_audit_log: {
              type: "boolean",
              description: "When true, includes last 5 authentication timestamps.",
            },
          },
          required: ["user_id"],
        },
      },
    ],
    destructive: [
      {
        name: "delete_workspace",
        description: "Deletes workspace records quickly.",
        inputSchema: {
          type: "object",
          properties: {
            workspace_id: { type: "string" },
            flag: { type: "boolean" },
          },
        },
      },
    ],
  };

  const BREAKER_SCENARIOS = {
    pingpong: [
      "Step 0: planner -> search_logs(query='timeout')   [cost=$0.0020] OK",
      "Step 1: planner -> refine_query(query='timeout')  [cost=$0.0021] OK",
      "Step 2: planner -> search_logs(query='timeout')   [cost=$0.0021] OK",
      "Step 3: planner -> refine_query(query='timeout')  [TRIPPED!]",
      "",
      "CircuitBreakerTripped:",
      "  rule: CB002 (ping_pong_oscillation)",
      "  evidence: { period: 2, cycles: 2, pattern: ['search_logs', 'refine_query'] }",
      "  action: aborted pre-execution; remaining budget preserved.",
    ],
    repeat: [
      "Step 0: sql.query(table='orders') [cost=$0.0018] OK",
      "Step 1: sql.query(table='orders') [cost=$0.0018] OK",
      "Step 2: sql.query(table='orders') [TRIPPED!]",
      "",
      "CircuitBreakerTripped:",
      "  rule: CB001 (identical_repeat_limit)",
      "  evidence: { count: 3, max_identical_repeats: 3, actor: 'sql.query' }",
    ],
    errors: [
      "Step 0: github.create_pr -> HTTP 422 ValidationError  [err_streak=1]",
      "Step 1: github.create_pr -> HTTP 422 ValidationError  [err_streak=2]",
      "Step 2: github.create_pr -> HTTP 422 ValidationError  [TRIPPED!]",
      "",
      "CircuitBreakerTripped:",
      "  rule: CB003 (consecutive_tool_errors)",
      "  evidence: { consecutive_errors: 3, actor: 'github.create_pr' }",
    ],
    budget: [
      "Step 0: llm_turn(gpt-4o)     [step_cost=$0.0410, total=$0.0410] OK",
      "Step 1: llm_turn(gpt-4o)     [step_cost=$0.0920, total=$0.1330] OK",
      "Step 2: llm_turn(gpt-4o)     [projected=+$0.1400 > cap] [TRIPPED!]",
      "",
      "CircuitBreakerTripped:",
      "  rule: CB004 (cost_budget_exceeded)",
      "  action: reserve_budget() blocked call before upstream HTTP dispatch.",
    ],
    clean: [
      "Step 0: planner_model -> plan(['query_metrics', 'fetch_deploys']) [cost=$0.0024] OK",
      "Step 1: prometheus.query_metrics(service='payment-api')           [cost=$0.0000] OK",
      "Step 2: github.fetch_recent_deploys(repo='payment-api')           [cost=$0.0000] OK",
      "Step 3: summarizer_model -> root cause report                     [cost=$0.0019] OK",
      "",
      "Status: PASS (4 spans, total_cost=$0.0043, 0 loops, SHA-256 chain sealed).",
    ],
  };

  const ARTIFACT_SAMPLES = {
    cassette: {
      title: "incident_8841.flight.json — Tamper-Evident SHA-256 Record",
      badge: "Cassette",
      code: HOME_PREVIEWS.cassette,
    },
    diff: {
      title: "diff-report.json — compare_cassettes Regression Check",
      badge: "CI Diff",
      code: JSON.stringify(
        {
          passed: true,
          similarity: 0.94,
          regression_detected: false,
          cost_delta_usd: -0.0004,
          cost_increase_pct: -12.5,
          added_tools: [],
          removed_tools: [],
        },
        null,
        2
      ),
    },
    otel: {
      title: "spans.otel.json — W3C TraceContext OpenTelemetry Spans",
      badge: "OTel Export",
      code: JSON.stringify(
        [
          {
            trace_id: "0af7651916cd43dd8448eb211c80319c",
            span_id: "b7ad6b7169203331",
            name: "mcp.rpc prometheus.query_metrics",
            attributes: {
              "gen_ai.system": "agentflight",
              "agentflight.step_index": 1,
              "agentflight.latency_ms": 88.2,
            },
          },
        ],
        null,
        2
      ),
    },
    postmortem: {
      title: "POST_MORTEM.md — AAIB/NTSB Incident Report",
      badge: "Post-Mortem",
      code: `# Flight Post-Mortem Incident Report\n- Severity: CRITICAL (Loop Oscillation)\n- Root Cause: Ping-pong cycle between search_logs and refine_query at step 3\n- SHA-256 Chain: VERIFIED (4 spans intact)\n- Total Cost Saved by Guard: ~$1.42 projected overshoot`,
    },
    doctor: {
      title: "doctor.json — Offline Production Readiness Diagnostics",
      badge: "Diagnostics",
      code: JSON.stringify(
        {
          healthy: true,
          version: "1.5.0",
          checks: [
            { name: "python_version", ok: true },
            { name: "stdlib_core", ok: true },
            { name: "pytest_plugin", ok: true },
            { name: "recorder_and_redaction", ok: true },
            { name: "circuit_breaker", ok: true },
          ],
        },
        null,
        2
      ),
    },
  };

  const RULE_ROWS = [
    { id: "TS001", pillar: "Schema Clarity", check: "Missing or short tool description (<15 chars) harms routing", sev: "ERROR (-12)" },
    { id: "TS002", pillar: "Schema Clarity", check: "Parameter missing semantic description inside properties", sev: "WARN (-5)" },
    { id: "TS003", pillar: "Structure & Bounds", check: "Deeply nested object schema (nesting depth > 3)", sev: "WARN (-8)" },
    { id: "TS004", pillar: "Structure & Bounds", check: "Excessive top-level parameter count (> 8 parameters)", sev: "WARN (-7)" },
    { id: "TS005", pillar: "Schema Clarity", check: "Ambiguous boolean flag name (flag, mode, option, toggle)", sev: "WARN (-5)" },
    { id: "TS006", pillar: "Structure & Bounds", check: "Unconstrained finite-set string (status, sort, env) missing enum", sev: "WARN (-6)" },
    { id: "TS007", pillar: "Structure & Bounds", check: "Non-empty schema missing required array", sev: "WARN (-6)" },
    { id: "TS008", pillar: "Suite & Safety", check: "High lexical overlap between suite tools (cosine >= 0.72)", sev: "ERROR (-10)" },
    { id: "TS009", pillar: "Structure & Bounds", check: "Schema definition token bloat (> 450 estimated tokens)", sev: "WARN (-7)" },
    { id: "TS010", pillar: "Suite & Safety", check: "Destructive tool (delete_/drop_/exec_) lacks confirm or dry_run", sev: "ERROR (-10)" },
    { id: "CB001", pillar: "Circuit Breakers", check: "Exact identical call + argument digest repeat guard", sev: "TRIP" },
    { id: "CB002", pillar: "Circuit Breakers", check: "Two-step or three-step ping-pong cycle detector (A->B->A->B)", sev: "TRIP" },
    { id: "CB003", pillar: "Circuit Breakers", check: "Consecutive tool error storm breaker", sev: "TRIP" },
    { id: "CB004", pillar: "Circuit Breakers", check: "Thread-safe USD spend cap & reserve_budget() shield", sev: "TRIP" },
    { id: "CB005", pillar: "Circuit Breakers", check: "Hard total prompt + completion token ceiling", sev: "TRIP" },
  ];

  const CHAPTER_ORDER = [
    { id: "getting-started", label: "Getting Started" },
    { id: "wrappers", label: "SDK Wrappers" },
    { id: "recorder", label: "Recorder & Replay" },
    { id: "pytest-ci", label: "Pytest & CI" },
    { id: "circuit-breaker", label: "Circuit Breaker" },
    { id: "mcp-server", label: "MCP Server" },
    { id: "post-mortem", label: "Post-Mortem & OTel" },
    { id: "openany", label: "OpenAny" },
    { id: "troubleshooting", label: "Troubleshooting" },
  ];

  function showToast(msg) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("visible");
    window.clearTimeout(el._t);
    el._t = window.setTimeout(() => el.classList.remove("visible"), 1900);
  }

  async function copyText(text, okMsg = "Copied to clipboard") {
    try {
      await navigator.clipboard.writeText(text);
      showToast(okMsg);
    } catch {
      showToast("Copy ready: select snippet manually");
    }
  }

  function normalizeCleanUrl() {
    if (window.location.protocol !== "https:") return;
    const { pathname, search, hash } = window.location;
    let nextPath = pathname;
    if (pathname.endsWith("/index.html")) {
      nextPath = pathname.slice(0, -"index.html".length);
    } else if (pathname.endsWith(".html")) {
      nextPath = pathname.slice(0, -".html".length);
    }
    if (nextPath !== pathname) {
      history.replaceState(null, "", `${nextPath}${search}${hash}`);
    }
  }

  function initCTA() {
    const mainBtn = $("#cta-main-btn");
    const caretBtn = $("#cta-caret-btn");
    const popover = $("#cta-popover");
    const heroCmd = $("#hero-cmd");
    const popCode = $("#pop-cmd-code");
    const popCopy = $("#pop-copy-btn");

    if (!mainBtn || !caretBtn || !popover) return;
    let currentKey = "pypi";

    function applyMode(key) {
      const m = INSTALL_MODES[key] || INSTALL_MODES.pypi;
      currentKey = key;
      if (heroCmd) heroCmd.textContent = m.caption;
      if (popCode) popCode.textContent = m.command;
      $$(".pop-tab").forEach((tab) => {
        const active = tab.dataset.persona === key;
        tab.classList.toggle("active", active);
        tab.setAttribute("aria-selected", String(active));
      });
    }

    function togglePopover(force) {
      const next = typeof force === "boolean" ? force : !popover.classList.contains("open");
      popover.classList.toggle("open", next);
      popover.hidden = !next;
      caretBtn.setAttribute("aria-expanded", String(next));
    }

    mainBtn.addEventListener("click", () => {
      const m = INSTALL_MODES[currentKey] || INSTALL_MODES.pypi;
      copyText(m.command, "Copied install command");
    });

    caretBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      togglePopover();
    });

    $$(".pop-tab").forEach((tab) => {
      tab.addEventListener("click", () => applyMode(tab.dataset.persona || "pypi"));
    });

    if (popCopy) {
      popCopy.addEventListener("click", () => {
        const m = INSTALL_MODES[currentKey] || INSTALL_MODES.pypi;
        copyText(m.command, "Copied command");
      });
    }

    document.addEventListener("click", (e) => {
      if (popover.classList.contains("open") && !popover.contains(e.target) && !caretBtn.contains(e.target)) {
        togglePopover(false);
      }
    });

    applyMode("pypi");
  }

  let avionicsCtx = null;
  function playAvionicsTone() {
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      if (!avionicsCtx) avionicsCtx = new AC();
      if (avionicsCtx.state === "suspended") avionicsCtx.resume();
      const notes = [440, 554.37, 659.25];
      const now = avionicsCtx.currentTime;
      notes.forEach((freq, i) => {
        const osc = avionicsCtx.createOscillator();
        const gain = avionicsCtx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(freq, now + i * 0.08);
        gain.gain.setValueAtTime(0.0001, now + i * 0.08);
        gain.gain.exponentialRampToValueAtTime(0.032, now + i * 0.08 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.08 + 0.14);
        osc.connect(gain);
        gain.connect(avionicsCtx.destination);
        osc.start(now + i * 0.08);
        osc.stop(now + i * 0.08 + 0.15);
      });
    } catch (err) {
      if (window.console && typeof window.console.debug === "function") {
        window.console.debug("WebAudio telemetry cue unavailable:", err);
      }
    }
  }

  function pulseFlightPipeline(containerId, stripId, withSound) {
    const strip = stripId ? document.getElementById(stripId) : null;
    if (strip) {
      strip.classList.add("playing");
      clearTimeout(strip._t);
      strip._t = setTimeout(() => strip.classList.remove("playing"), 1500);
    }
    const container = containerId ? document.getElementById(containerId) : null;
    if (container) {
      const stages = container.querySelectorAll(".flight-stage");
      stages.forEach((st, idx) => {
        setTimeout(() => {
          stages.forEach((s) => s.classList.remove("active"));
          st.classList.add("active");
        }, idx * 240);
      });
    }
    if (withSound) playAvionicsTone();
  }

  function initFlightAnimations() {
    const reveals = $$(".reveal");
    const metricBars = $$(".metric-bar-fill[data-width]");

    function fillBars() {
      metricBars.forEach((bar) => {
        const target = bar.getAttribute("data-width") || "0%";
        requestAnimationFrame(() => {
          bar.style.width = target;
        });
      });
    }

    if ("IntersectionObserver" in window && reveals.length > 0) {
      const obs = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("in-view");
              obs.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.08 }
      );
      reveals.forEach((el) => obs.observe(el));
      setTimeout(fillBars, 120);
    } else {
      reveals.forEach((el) => el.classList.add("in-view"));
      fillBars();
    }

    const playFlightBtn = $("#play-flight-btn");
    if (playFlightBtn) {
      playFlightBtn.addEventListener("click", () => {
        pulseFlightPipeline("home-pipeline", "home-telemetry-strip", true);
      });
    }

    const studioFlightBtn = $("#studio-flight-btn");
    if (studioFlightBtn) {
      studioFlightBtn.addEventListener("click", () => {
        pulseFlightPipeline("studio-pipeline", "studio-telemetry-strip", true);
      });
    }

    const flightNote = $("#flight-sample-note");
    const previewCode = $("#home-preview-code");
    const SCENARIO_CODE = {
      demo: HOME_PREVIEWS.term,
      breaker: `$ agentflight guard --scenario pingpong --max-usd 0.25\n\nCircuitBreakerTripped [CB002 ping_pong_oscillation]\n  Pattern:  ['search_logs', 'refine_query'] x 2 cycles\n  Action:   Aborted pre-execution; $1.42 projected overshoot saved`,
      redact: `$ agentflight record --scrub-secrets --out incident.flight.json\n\nFlightRecorder · Secret Scrubber Enabled\n  Detected: sk-live-***, Bearer eyJ*** -> [REDACTED_SECRET]\n  Digest:   SHA-256 chain intact (genesis -> span 4)`,
      pytest: `$ pytest -v --flight-mode=replay\n\n========================= 42 passed in 0.14s =========================\n  Replayed: 168 spans (2.83 us avg) · Live LLM Spend: $0.0000`,
      otel: `$ agentflight export-otel incident.flight.json --out spans.otel.json\n\nExported 4 W3C TraceContext spans (gen_ai.system = "agentflight")\n  trace_id: 0af7651916cd43dd8448eb211c80319c`,
      lint: HOME_PREVIEWS.linter,
    };

    $$(".flight-chip[data-flight-note]").forEach((chip) => {
      chip.addEventListener("click", () => {
        $$(".flight-chip[data-flight-note]").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        if (flightNote) flightNote.textContent = chip.getAttribute("data-flight-note");
        const key = chip.getAttribute("data-flight-key") || "";
        if (previewCode && SCENARIO_CODE[key]) {
          previewCode.textContent = SCENARIO_CODE[key];
        }
        pulseFlightPipeline("home-pipeline", "home-telemetry-strip", false);
      });
    });

    $$("[data-bench-filter]").forEach((chip) => {
      chip.addEventListener("click", () => {
        $$("[data-bench-filter]").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        const target = chip.getAttribute("data-bench-filter") || "all";
        $$("tbody tr[data-bench-cat]").forEach((row) => {
          const cat = row.getAttribute("data-bench-cat") || "";
          row.style.display = target === "all" || cat === target ? "" : "none";
        });
      });
    });
  }

  function initHomePreview() {
    const pre = $("#home-preview-code");
    const tabs = $$("[data-homeview]");
    if (!pre || tabs.length === 0) return;

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const key = tab.dataset.homeview || "term";
        pre.textContent = HOME_PREVIEWS[key] || HOME_PREVIEWS.term;
        tabs.forEach((t) => {
          const active = t === tab;
          t.classList.toggle("active", active);
          t.setAttribute("aria-selected", String(active));
        });
        pulseFlightPipeline("home-pipeline", "home-telemetry-strip", false);
      });
    });
  }

  function initCopyButtons() {
    $$("[data-copy]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const val = btn.getAttribute("data-copy") || "";
        if (val) copyText(val);
      });
    });
  }

  function initInstallTabs() {
    const tabs = $$("[data-install]");
    const eyebrow = $("#inst-eyebrow");
    const note = $("#inst-note");
    const codeEl = $("#inst-code");
    const copyBtn = $("#inst-copy-btn");
    if (tabs.length === 0 || !codeEl) return;

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const key = tab.dataset.install || "pypi";
        const cfg = DOC_INSTALL_PRESETS[key] || DOC_INSTALL_PRESETS.pypi;
        tabs.forEach((t) => {
          const active = t === tab;
          t.classList.toggle("active", active);
          t.setAttribute("aria-selected", String(active));
        });
        if (eyebrow) eyebrow.textContent = cfg.eyebrow;
        if (note) note.textContent = cfg.note;
        codeEl.textContent = cfg.code;
        if (copyBtn) copyBtn.setAttribute("data-copy", cfg.code);
      });
    });
  }

  function initDocsNavigation() {
    const titleEl = $("#doc-chapter-title");
    const chapters = $$(".doc-chapter[data-chapter]");
    if (!titleEl || chapters.length === 0) return;

    const prevBtn = $("#doc-prev");
    const prevLbl = $("#doc-prev-label");
    const nextBtn = $("#doc-next");
    const nextLbl = $("#doc-next-label");
    let currentChapter = "getting-started";

    function highlightSubAnchor(anchorId) {
      $$(".doc-sub-link").forEach((link) => {
        const hrefId = (link.getAttribute("href") || "").replace(/^#/, "");
        link.classList.toggle("active", hrefId === anchorId);
      });
    }

    function openChapter(chapterId, scrollTargetId, scrollToTop = true) {
      const idx = CHAPTER_ORDER.findIndex((c) => c.id === chapterId);
      const entry = idx >= 0 ? CHAPTER_ORDER[idx] : CHAPTER_ORDER[0];
      const activeIdx = idx >= 0 ? idx : 0;
      currentChapter = entry.id;

      titleEl.textContent = entry.label;
      chapters.forEach((sec) => {
        const match = sec.dataset.chapter === entry.id;
        if (match) sec.removeAttribute("hidden");
        else sec.setAttribute("hidden", "");
      });

      $$(".doc-nav-link[data-doc-target]").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.docTarget === entry.id);
      });
      $$(".docs-mobile-chip[data-doc-target]").forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.docTarget === entry.id);
      });
      $$(".doc-subrail[data-subrail]").forEach((rail) => {
        rail.classList.toggle("open", rail.dataset.subrail === entry.id);
      });

      if (prevBtn && prevLbl) {
        if (activeIdx > 0) {
          prevBtn.removeAttribute("hidden");
          prevBtn.dataset.jumpIndex = String(activeIdx - 1);
          prevLbl.textContent = `← ${CHAPTER_ORDER[activeIdx - 1].label}`;
        } else {
          prevBtn.setAttribute("hidden", "");
        }
      }

      if (nextBtn && nextLbl) {
        if (activeIdx < CHAPTER_ORDER.length - 1) {
          nextBtn.removeAttribute("hidden");
          nextBtn.dataset.jumpIndex = String(activeIdx + 1);
          nextLbl.textContent = `${CHAPTER_ORDER[activeIdx + 1].label} →`;
        } else {
          nextBtn.setAttribute("hidden", "");
        }
      }

      if (scrollTargetId) {
        const el = document.getElementById(scrollTargetId);
        if (el) {
          highlightSubAnchor(scrollTargetId);
          requestAnimationFrame(() => el.scrollIntoView({ behavior: "smooth", block: "start" }));
          return;
        }
      }

      const firstSub = $(`.doc-subrail[data-subrail="${entry.id}"] .doc-sub-link`);
      if (firstSub) {
        highlightSubAnchor((firstSub.getAttribute("href") || "").replace(/^#/, ""));
      }
      if (scrollToTop) window.scrollTo({ top: 0, behavior: "smooth" });
    }

    $$(".doc-nav-link[data-doc-target], .docs-mobile-chip[data-doc-target]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.dataset.docTarget;
        history.replaceState(null, "", `#${target}`);
        openChapter(target);
      });
    });

    $$(".doc-sub-link[data-doc-anchor]").forEach((link) => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const ch = link.dataset.docAnchor;
        const hashId = (link.getAttribute("href") || "").replace(/^#/, "");
        history.replaceState(null, "", `#${hashId}`);
        openChapter(ch, hashId);
      });
    });

    if (prevBtn) {
      prevBtn.addEventListener("click", () => {
        const nextIdx = Number(prevBtn.dataset.jumpIndex || "0");
        const entry = CHAPTER_ORDER[nextIdx];
        if (entry) {
          history.replaceState(null, "", `#${entry.id}`);
          openChapter(entry.id);
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", () => {
        const nextIdx = Number(nextBtn.dataset.jumpIndex || "1");
        const entry = CHAPTER_ORDER[nextIdx];
        if (entry) {
          history.replaceState(null, "", `#${entry.id}`);
          openChapter(entry.id);
        }
      });
    }

    window.addEventListener(
      "scroll",
      () => {
        const activePanel = $(`.doc-chapter[data-chapter="${currentChapter}"]`);
        if (!activePanel) return;
        const headings = Array.from(activePanel.querySelectorAll("h2[id], h3[id]"));
        let best = headings[0];
        for (const h of headings) {
          if (h.getBoundingClientRect().top <= 130) best = h;
        }
        if (best && best.id) highlightSubAnchor(best.id);
      },
      { passive: true }
    );

    const rawHash = (window.location.hash || "").replace(/^#/, "");
    if (rawHash) {
      if (CHAPTER_ORDER.some((c) => c.id === rawHash)) {
        openChapter(rawHash);
      } else {
        const anchorEl = document.getElementById(rawHash);
        const owner = anchorEl && anchorEl.closest(".doc-chapter[data-chapter]");
        if (owner) {
          openChapter(owner.dataset.chapter, rawHash);
        } else {
          openChapter("getting-started", null, false);
        }
      }
    } else {
      openChapter("getting-started", null, false);
    }
  }

  function initStudioTabs() {
    const tabs = $$("[data-studio]");
    if (tabs.length === 0) return;
    const panels = {
      lint: $("#panel-lint"),
      breaker: $("#panel-breaker"),
      outputs: $("#panel-outputs"),
    };

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const target = tab.dataset.studio;
        tabs.forEach((t) => {
          const active = t === tab;
          t.classList.toggle("active", active);
          t.setAttribute("aria-selected", String(active));
        });
        Object.entries(panels).forEach(([k, el]) => {
          if (el) el.classList.toggle("active", k === target);
        });
      });
    });
  }

  function measureDepth(obj, depth = 0) {
    if (!obj || typeof obj !== "object") return depth;
    const props = obj.properties;
    if (!props || typeof props !== "object") return depth;
    let maxD = depth + 1;
    Object.values(props).forEach((val) => {
      maxD = Math.max(maxD, measureDepth(val, depth + 1));
    });
    return maxD;
  }

  function lintToolsClient(tools) {
    const findings = [];
    const tokens = Math.round(JSON.stringify(tools).length / 4);
    const destructiveRe = /^(delete|drop|remove|transfer|exec)_/i;
    const enumHintNames = new Set(["status", "sort", "format", "env", "role", "type", "priority"]);
    const boolAmbiguous = new Set(["flag", "mode", "option", "data", "value", "switch", "toggle"]);

    tools.forEach((t) => {
      const name = String(t.name || "unnamed");
      const desc = String(t.description || "");
      const schema = t.inputSchema && typeof t.inputSchema === "object" ? t.inputSchema : {};
      const props = schema.properties && typeof schema.properties === "object" ? schema.properties : {};
      const req = Array.isArray(schema.required) ? schema.required : [];
      const propNames = Object.keys(props);

      if (desc.trim().length < 15) {
        findings.push({ rule: "TS001", penalty: 12, text: `${name}: tool description under 15 chars (${desc.trim().length}).` });
      }
      propNames.forEach((p) => {
        const spec = props[p] || {};
        if (!spec.description || String(spec.description).trim().length < 4) {
          findings.push({ rule: "TS002", penalty: 5, text: `${name}.${p}: parameter missing description.` });
        }
        if (spec.type === "boolean" && boolAmbiguous.has(p.toLowerCase())) {
          findings.push({ rule: "TS005", penalty: 5, text: `${name}.${p}: ambiguous boolean flag name.` });
        }
        if (spec.type === "string" && enumHintNames.has(p.toLowerCase()) && !spec.enum && !spec.pattern) {
          findings.push({ rule: "TS006", penalty: 6, text: `${name}.${p}: finite string lacks enum or pattern.` });
        }
      });

      if (measureDepth(schema) > 3) {
        findings.push({ rule: "TS003", penalty: 8, text: `${name}: object schema nesting depth exceeds 3.` });
      }
      if (propNames.length > 8) {
        findings.push({ rule: "TS004", penalty: 7, text: `${name}: too many top-level parameters (${propNames.length} > 8).` });
      }
      if (propNames.length > 0 && req.length === 0) {
        findings.push({ rule: "TS007", penalty: 6, text: `${name}: non-empty schema omits required array.` });
      }
      if (Math.round(JSON.stringify(t).length / 4) > 450) {
        findings.push({ rule: "TS009", penalty: 7, text: `${name}: schema footprint exceeds 450 tokens.` });
      }
      if (destructiveRe.test(name) && !propNames.some((k) => ["confirm", "dry_run", "idempotency_key"].includes(k))) {
        findings.push({ rule: "TS010", penalty: 10, text: `${name}: destructive tool lacks confirm, dry_run, or idempotency_key.` });
      }
    });

    if (tools.length >= 2) {
      const a = new Set(String(tools[0].name + " " + tools[0].description).toLowerCase().split(/\W+/).filter(Boolean));
      const b = new Set(String(tools[1].name + " " + tools[1].description).toLowerCase().split(/\W+/).filter(Boolean));
      const inter = Array.from(a).filter((w) => b.has(w)).length;
      const cos = a.size && b.size ? inter / Math.sqrt(a.size * b.size) : 0;
      if (cos >= 0.45) {
        findings.push({ rule: "TS008", penalty: 10, text: `${tools[0].name} <-> ${tools[1].name}: high lexical overlap between sibling tools.` });
      }
    }

    const totalPenalty = findings.reduce((acc, f) => acc + f.penalty, 0);
    const score = Math.max(0, 100 - totalPenalty);
    const grade = score >= 95 ? "A+" : score >= 90 ? "A" : score >= 80 ? "B" : score >= 70 ? "C" : score >= 60 ? "D" : "F";
    return { score, grade, errors: findings.length, tokens, findings };
  }

  function initLinterStudio() {
    const inputEl = $("#lint-json-input");
    const scoreEl = $("#lint-score");
    const gradeEl = $("#lint-grade");
    const errEl = $("#lint-errors");
    const tokEl = $("#lint-tokens");
    const sumEl = $("#lint-summary");
    const listEl = $("#lint-findings");
    if (!inputEl || !scoreEl) return;

    function runLint() {
      let parsed;
      try {
        parsed = JSON.parse(inputEl.value);
        if (!Array.isArray(parsed)) parsed = [parsed];
      } catch (err) {
        scoreEl.textContent = "Err";
        gradeEl.textContent = "—";
        errEl.textContent = "1";
        if (sumEl) sumEl.textContent = `Invalid JSON syntax: ${err.message}`;
        if (listEl) listEl.replaceChildren();
        return;
      }

      const res = lintToolsClient(parsed);
      scoreEl.textContent = `${res.score} / 100`;
      gradeEl.textContent = res.grade;
      errEl.textContent = String(res.errors);
      tokEl.textContent = String(res.tokens);
      if (sumEl) {
        sumEl.textContent = res.findings.length
          ? `Detected ${res.findings.length} tool smell(s). Run agentflight fix to harden schemas automatically.`
          : "All 10 static MCP tool ergonomics checks passed (Glama Gold Standard).";
      }
      if (listEl) {
        const items = res.findings.map((f) => {
          const box = document.createElement("div");
          box.className = f.penalty >= 10 ? "rw-item warn-border" : "rw-item";
          const tag = document.createElement("span");
          tag.textContent = `${f.rule} (-${f.penalty})`;
          const p = document.createElement("p");
          p.textContent = f.text;
          box.append(tag, p);
          return box;
        });
        listEl.replaceChildren(...items);
      }
    }

    inputEl.value = JSON.stringify(LINTER_PRESETS.flawed, null, 2);
    runLint();

    inputEl.addEventListener("input", runLint);
      $$("[data-lint-preset]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.lintPreset || "flawed";
        $$("[data-lint-preset]").forEach((b) => b.classList.toggle("active", b === btn));
        inputEl.value = JSON.stringify(LINTER_PRESETS[key] || LINTER_PRESETS.flawed, null, 2);
        runLint();
        pulseFlightPipeline("studio-pipeline", "studio-telemetry-strip", false);
      });
    });
  }

  function initBreakerSimulator() {
    const scenEl = $("#cb-scenario");
    const capEl = $("#cb-budget");
    const outEl = $("#cb-output");
    const runBtn = $("#cb-run-btn");
    const copyBtn = $("#cb-copy-btn");
    if (!scenEl || !outEl) return;

    function render() {
      const scen = scenEl.value || "pingpong";
      const cap = (capEl && capEl.value) || "0.25";
      const lines = [...(BREAKER_SCENARIOS[scen] || BREAKER_SCENARIOS.pingpong)];
      lines.unshift(`TrajectoryCircuitBreaker(max_identical_repeats=3, max_ping_pong_cycles=2, max_cost_usd=${cap})\n`);
      outEl.textContent = lines.join("\n");
      pulseFlightPipeline("studio-pipeline", "studio-telemetry-strip", false);
    }

    if (runBtn) runBtn.addEventListener("click", render);
    scenEl.addEventListener("change", render);
    if (capEl) capEl.addEventListener("change", render);
    if (copyBtn) copyBtn.addEventListener("click", () => copyText(outEl.textContent || "", "Copied trace"));
    render();
  }

  function initOutputs() {
    const titleEl = $("#out-title");
    const badgeEl = $("#out-badge");
    const codeEl = $("#out-code");
    const copyBtn = $("#out-copy-btn");
    if (!codeEl) return;

    function selectOutput(key) {
      const item = ARTIFACT_SAMPLES[key] || ARTIFACT_SAMPLES.cassette;
      if (titleEl) titleEl.textContent = item.title;
      if (badgeEl) badgeEl.textContent = item.badge;
      codeEl.textContent = item.code;
      $$("[data-out]").forEach((b) => b.classList.toggle("active", b.dataset.out === key));
    }

    $$("[data-out]").forEach((btn) => {
      btn.addEventListener("click", () => selectOutput(btn.dataset.out || "cassette"));
    });

    if (copyBtn) copyBtn.addEventListener("click", () => copyText(codeEl.textContent || "", "Copied artifact"));
    selectOutput("cassette");
  }

  function initProof() {
    const badge = $("#cs-badge");
    const title = $("#cs-title");
    const list = $("#cs-list");
    const tabs = $$("[data-stage]");
    if (!badge || tabs.length === 0) return;

    const states = {
      before: {
        cls: "pill pill-amber",
        badge: "Grade F • 7 findings detected",
        title: "Short descriptions, unconstrained strings, and unguarded delete_tool",
        items: [
          "TS001 (-12) Tool description under 15 chars left model routing ambiguous.",
          "TS005 (-5) Boolean flag mode had unclear polarity without explicit description.",
          "TS006 (-6) Unconstrained status string lacked an explicit enum list.",
          "TS010 (-10) Destructive delete_record lacked confirm or dry_run guard.",
        ],
      },
      after: {
        cls: "pill pill-good",
        badge: "Grade A+ • 0 smells remaining",
        title: "Hardened schemas verified at 1,676 tools/sec",
        items: [
          "100/100 Ergonomics Score verified statically by ToolSmellLinter.",
          "Explicit enums, required arrays, and confirm: boolean safety guard injected.",
          "1,676 tools/sec static gate ready for GitHub Actions pull requests.",
          "Zero runtime dependencies; safe for offline regulated environments.",
        ],
      },
    };

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const key = tab.dataset.stage || "before";
        const s = states[key] || states.before;
        tabs.forEach((t) => {
          const active = t === tab;
          t.classList.toggle("active", active);
          t.setAttribute("aria-selected", String(active));
        });
        badge.className = s.cls;
        badge.textContent = s.badge;
        if (title) title.textContent = s.title;
        if (list) {
          list.replaceChildren(
            ...s.items.map((txt) => {
              const li = document.createElement("li");
              li.textContent = txt;
              return li;
            })
          );
        }
      });
    });
  }

  function initRubric() {
    const tbody = $("#rules-tbody");
    const searchEl = $("#rule-search");
    const pillarEl = $("#rule-pillar");
    if (!tbody) return;

    function renderRules() {
      const q = ((searchEl && searchEl.value) || "").trim().toLowerCase();
      const pil = (pillarEl && pillarEl.value) || "all";

      const matched = RULE_ROWS.filter((r) => {
        if (pil !== "all" && r.pillar !== pil) return false;
        if (!q) return true;
        return `${r.id} ${r.pillar} ${r.check} ${r.sev}`.toLowerCase().includes(q);
      });

      const rows = matched.map((r) => {
        const tr = document.createElement("tr");
        const tdId = document.createElement("td");
        const code = document.createElement("code");
        code.textContent = r.id;
        tdId.appendChild(code);

        const tdPil = document.createElement("td");
        tdPil.textContent = r.pillar;

        const tdCheck = document.createElement("td");
        tdCheck.textContent = r.check;

        const tdSev = document.createElement("td");
        const span = document.createElement("span");
        span.className = r.sev.startsWith("ERROR")
          ? "pill pill-bad"
          : r.sev === "TRIP"
            ? "pill pill-amber"
            : "pill pill-sky";
        span.textContent = r.sev;
        tdSev.appendChild(span);

        tr.append(tdId, tdPil, tdCheck, tdSev);
        return tr;
      });

      tbody.replaceChildren(...rows);
    }

    if (searchEl) searchEl.addEventListener("input", renderRules);
    if (pillarEl) {
      pillarEl.addEventListener("change", () => {
        const val = pillarEl.value;
        $$("[data-pillarfilter]").forEach((btn) => {
          btn.classList.toggle("active", btn.dataset.pillarfilter === val);
        });
        renderRules();
      });
    }

    $$("[data-pillarfilter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const val = btn.dataset.pillarfilter || "all";
        if (pillarEl) pillarEl.value = val;
        $$("[data-pillarfilter]").forEach((b) => {
          b.classList.toggle("active", b.dataset.pillarfilter === val);
        });
        renderRules();
      });
    });

    renderRules();
  }

  document.addEventListener("DOMContentLoaded", () => {
    normalizeCleanUrl();
    initCTA();
    initHomePreview();
    initFlightAnimations();
    initCopyButtons();
    initInstallTabs();
    initDocsNavigation();
    initStudioTabs();
    initLinterStudio();
    initBreakerSimulator();
    initOutputs();
    initProof();
    initRubric();
  });
})();
