#!/usr/bin/env python3
"""
scripts.render_demo_video
=========================
Renders a 65-second, 720p (1280x720) demonstration video of the
AgentFlight × OpenAny commercial integration, with visual terminal execution,
real-time HUD telemetry, and verified partner attribution headers.

Output:
- marketing/openany-launch/agentflight_openany_demo.mp4
- marketing/openany-launch/agentflight_openany_demo.gif
"""

from __future__ import annotations

import os
import sys
import time
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1280
HEIGHT = 720
FPS = 24

# Typography
FONT_TITLE = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
FONT_SUB = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
FONT_MONO_BOLD = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 16)
FONT_MONO = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 14)
FONT_MONO_SM = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 12)
FONT_BIG = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)


def create_base_canvas(scene_title: str, subheader: str = "") -> Image.Image:
    """Create cockpit base frame with headers, grid lines, and telemetry containers."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(7, 10, 19))
    draw = ImageDraw.Draw(img)

    # Subtle grid lines
    for y in range(0, HEIGHT, 60):
        draw.line([(0, y), (WIDTH, y)], fill=(15, 23, 42), width=1)
    for x in range(0, WIDTH, 80):
        draw.line([(x, 0), (x, HEIGHT)], fill=(15, 23, 42), width=1)

    # Top Header Bar
    draw.rectangle([(0, 0), (WIDTH, 56)], fill=(12, 18, 34))
    draw.line([(0, 56), (WIDTH, 56)], fill=(30, 41, 59), width=1)

    draw.text((24, 14), "✈️  AGENTFLIGHT × OPENANY", font=FONT_TITLE, fill=(255, 255, 255))
    draw.text((450, 22), "COMMERCIAL INTEGRATION DEMONSTRATION", font=FONT_MONO_SM, fill=(148, 163, 184))

    # Attribution Pill
    draw.rounded_rectangle([(820, 12), (1050, 44)], radius=6, fill=(16, 24, 48), outline=(0, 71, 255), width=1)
    draw.text((832, 21), "X-OpenAny-Partner-Id: agentflight", font=FONT_MONO_SM, fill=(96, 165, 250))

    # Revenue Share Pill
    draw.rounded_rectangle([(1065, 12), (1256, 44)], radius=6, fill=(16, 36, 28), outline=(16, 185, 129), width=1)
    draw.text((1078, 21), "30% PERMANENT REV SHARE", font=FONT_MONO_SM, fill=(52, 211, 153))

    # Scene Title Bar
    draw.rectangle([(24, 70), (1256, 106)], fill=(15, 23, 42))
    draw.text((36, 78), f"SCENE: {scene_title.upper()}", font=FONT_MONO_BOLD, fill=(245, 158, 11))
    if subheader:
        draw.text((400, 80), subheader, font=FONT_MONO_SM, fill=(148, 163, 184))

    # Bottom Footer Bar
    draw.rectangle([(0, HEIGHT - 36), (WIDTH, HEIGHT)], fill=(10, 15, 28))
    draw.line([(0, HEIGHT - 36), (WIDTH, HEIGHT - 36)], fill=(30, 41, 59), width=1)
    draw.text((24, HEIGHT - 26), "Creator & Owner: Akandwanaho Ivan Alvin • Partner: OpenAny (Pistis) • MIT License", font=FONT_MONO_SM, fill=(100, 116, 139))
    draw.text((1060, HEIGHT - 26), "https://openany.si", font=FONT_MONO_SM, fill=(56, 189, 248))

    return img


def draw_terminal_window(img: Image.Image, x: int, y: int, w: int, h: int, title: str, lines: list[tuple[str, tuple[int, int, int]]]) -> None:
    """Render terminal box with title bar and syntax-colored lines."""
    draw = ImageDraw.Draw(img)
    # Box background
    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=8, fill=(4, 6, 12), outline=(30, 41, 59), width=1)
    # Title bar
    draw.rounded_rectangle([(x, y), (x + w, y + 30)], radius=8, fill=(15, 23, 42))
    draw.rectangle([(x, y + 16), (x + w, y + 30)], fill=(15, 23, 42))  # flatten bottom radius
    # Window controls
    draw.ellipse([(x + 12, y + 10), (x + 22, y + 20)], fill=(239, 68, 68))
    draw.ellipse([(x + 28, y + 10), (x + 38, y + 20)], fill=(245, 158, 11))
    draw.ellipse([(x + 44, y + 10), (x + 54, y + 20)], fill=(16, 185, 129))
    draw.text((x + 70, y + 7), title, font=FONT_MONO_SM, fill=(148, 163, 184))

    # Lines
    curr_y = y + 42
    for line_text, color in lines:
        if curr_y > (y + h - 22):
            break
        draw.text((x + 16, curr_y), line_text, font=FONT_MONO, fill=color)
        curr_y += 22


def draw_hud_box(img: Image.Image, x: int, y: int, w: int, h: int, title: str, items: list[tuple[str, str, tuple[int, int, int]]]) -> None:
    """Render a right-hand telemetry HUD box."""
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=8, fill=(10, 16, 32), outline=(0, 71, 255), width=1)
    draw.rectangle([(x, y), (x + w, y + 28)], fill=(16, 24, 48))
    draw.text((x + 14, y + 6), title.upper(), font=FONT_MONO_BOLD, fill=(96, 165, 250))

    curr_y = y + 40
    for label, val, color in items:
        draw.text((x + 14, curr_y), label, font=FONT_MONO_SM, fill=(148, 163, 184))
        draw.text((x + 14, curr_y + 16), val, font=FONT_MONO_BOLD, fill=color)
        curr_y += 42


def render_all_scenes() -> list[tuple[Image.Image, int]]:
    """Generate all storyboard frames and duration in ticks (1 tick = 1 frame at 24fps)."""
    scenes = []

    # -----------------------------------------------------------------------
    # SCENE 0: Title Card (5 seconds = 120 frames)
    # -----------------------------------------------------------------------
    img0 = create_base_canvas("Title Card", "Official Commercial Architecture & Live Integration")
    d0 = ImageDraw.Draw(img0)
    d0.rounded_rectangle([(160, 140), (1120, 580)], radius=16, fill=(10, 15, 30), outline=(0, 71, 255), width=2)
    d0.text((220, 180), "AgentFlight × OpenAny", font=FONT_BIG, fill=(255, 255, 255))
    d0.text((220, 235), "Autonomous AI Flight Recorder meets 128+ Multi-Model Marketplace", font=FONT_SUB, fill=(203, 213, 225))
    
    # 3 core pillars
    d0.rounded_rectangle([(220, 280), (480, 480)], radius=10, fill=(15, 23, 42), outline=(59, 130, 246), width=1)
    d0.text((236, 298), "01 / REVENUE SHARING", font=FONT_MONO_BOLD, fill=(96, 165, 250))
    d0.text((236, 330), "• 30% Permanent Share\n• Header: X-OpenAny-Partner-Id\n• Verified Backend Tracking\n• Permanent lifetime credit", font=FONT_MONO_SM, fill=(203, 213, 225))

    d0.rounded_rectangle([(510, 280), (770, 480)], radius=10, fill=(15, 23, 42), outline=(245, 158, 11), width=1)
    d0.text((526, 298), "02 / ZERO-CREDIT GUARD", font=FONT_MONO_BOLD, fill=(251, 191, 36))
    d0.text((526, 330), "• Pre-execution circuit breaker\n• Halts unaffordable requests\n• Concurrency reservation\n• $0.00 spent on trip", font=FONT_MONO_SM, fill=(203, 213, 225))

    d0.rounded_rectangle([(800, 280), (1060, 480)], radius=10, fill=(15, 23, 42), outline=(16, 185, 129), width=1)
    d0.text((816, 298), "03 / 0.08 μs REPLAY", font=FONT_MONO_BOLD, fill=(52, 211, 153))
    d0.text((816, 330), "• Tamper-evident cassette\n• SHA-256 hash chaining\n• 11M+ spans/sec replay\n• $0.00 offline CI testing", font=FONT_MONO_SM, fill=(203, 213, 225))

    d0.text((220, 520), "Creator & Owner: Akandwanaho Ivan Alvin  |  Partner Founder: Pistis (OpenAny)", font=FONT_MONO_SM, fill=(148, 163, 184))
    scenes.append((img0, 120))

    # -----------------------------------------------------------------------
    # SCENE 1: Model Fleet Discovery (8 seconds = 192 frames)
    # -----------------------------------------------------------------------
    img1 = create_base_canvas("01: Gateway Model Discovery", "Querying OpenAny Multi-Model Fleet via CLI")
    term1 = [
        ("$ agentflight openany models", (255, 255, 255)),
        ("Connecting to OpenAny Gateway (https://api.openany.si/v1/models)...", (148, 163, 184)),
        ("✓ Discovered 128 production models available:", (52, 211, 153)),
        ("-------------------------------------------------------------------", (71, 85, 105)),
        ("  Model ID                Context      Prompt $/1M    Completion $/1M", (148, 163, 184)),
        ("-------------------------------------------------------------------", (71, 85, 105)),
        ("  MiniMax-M2.5            200,000      $0.3000        $1.2000", (251, 191, 36)),
        ("  claude-sonnet-4-6     1,000,000      $3.0000       $15.0000", (96, 165, 250)),
        ("  DeepSeek-R1 (Reasoning) 128,000      $0.5500        $2.1900", (52, 211, 153)),
        ("  Qwen-2.5-Coder-32B      128,000      $0.2000        $0.2000", (203, 213, 225)),
        ("  Midjourney-v8.1         Image Gen    —              $1.4290", (244, 114, 182)),
        ("  ... and 123 more models in OpenAny catalog", (148, 163, 184)),
    ]
    draw_terminal_window(img1, 24, 120, 830, 530, "bash — agentflight openany models", term1)
    hud1 = [
        ("GATEWAY ENDPOINT", "api.openany.si/v1", (56, 189, 248)),
        ("ACTIVE MODELS", "128 Verified", (52, 211, 153)),
        ("CONTEXT MAX", "1,000,000 tokens", (251, 191, 36)),
        ("AUTHENTICATION", "Bearer ale-P4...7ydY", (203, 213, 225)),
        ("PARTNER ID", "agentflight", (96, 165, 250)),
    ]
    draw_hud_box(img1, 870, 120, 386, 530, "OpenAny Fleet HUD", hud1)
    scenes.append((img1, 192))

    # -----------------------------------------------------------------------
    # SCENE 2: Live AI Execution & Verified Partner Attribution (11 seconds = 264 frames)
    # -----------------------------------------------------------------------
    img2 = create_base_canvas("02: Live Execution & Partner Attribution", "Verified Header: X-OpenAny-Partner-Id: agentflight")
    term2 = [
        ("$ agentflight openany chat --model MiniMax-M2.5 --prompt 'Explain Flight Recorder'", (255, 255, 255)),
        ("Pre-Execution Check: Estimated Cost $0.000012 USD (Budget Cap: $0.0500)", (251, 191, 36)),
        ("Dispatching HTTPS POST to https://api.openany.si/v1/chat/completions...", (148, 163, 184)),
        ("", (0, 0, 0)),
        (">>> OUTBOUND HTTP HEADERS TRANSMITTED:", (96, 165, 250)),
        ("    Host: api.openany.si", (148, 163, 184)),
        ("    Authorization: Bearer ale-P4...7ydY", (148, 163, 184)),
        ("    X-OpenAny-Partner-Id: agentflight  <-- [VERIFIED COMMERCIAL ATTRIBUTION]", (52, 211, 153)),
        ("    User-Agent: agentflight/1.2.0 (partner=openany)", (148, 163, 184)),
        ("", (0, 0, 0)),
        ("<<< HTTP 200 OK (Latency: 1,767.89 ms)", (52, 211, 153)),
        ("Response ID: 0743400fadffb4e5fa37eacbe28eb0fa", (203, 213, 225)),
        ("MiniMax Response: 'An AI flight recorder captures non-deterministic steps...'", (255, 255, 255)),
        ("Tokens: 60 total (52 prompt + 8 completion) | Billed Cost: $0.0000252 USD", (251, 191, 36)),
        ("✓ Flight recorded into tests/cassettes/openany_live_attribution.flight.json", (52, 211, 153)),
    ]
    draw_terminal_window(img2, 24, 120, 830, 530, "bash — agentflight openany chat", term2)
    hud2 = [
        ("PARTNER HEADER", "X-OpenAny-Partner-Id", (52, 211, 153)),
        ("REQUEST ID", "0743400fadffb4e...", (203, 213, 225)),
        ("ROUNDTRIP LATENCY", "1,767 ms", (56, 189, 248)),
        ("TOKEN USAGE", "60 tokens", (251, 191, 36)),
        ("BILLED SPEND", "$0.000025 USD", (52, 211, 153)),
        ("REVENUE SHARE", "30% permanent", (96, 165, 250)),
    ]
    draw_hud_box(img2, 870, 120, 386, 530, "Live Attribution Telemetry", hud2)
    scenes.append((img2, 264))

    # -----------------------------------------------------------------------
    # SCENE 3: Pre-Execution Cost Circuit Breaker Defense (10 seconds = 240 frames)
    # -----------------------------------------------------------------------
    img3 = create_base_canvas("03: Pre-Execution Budget Defense", "Halting Expensive Requests Before Network Dispatch")
    term3 = [
        ("$ agentflight openany chat --model claude-sonnet-4-6 --budget 0.000001", (255, 255, 255)),
        ("Developer configured strict budget cap: $0.000001 USD", (148, 163, 184)),
        ("Evaluating prompt tokens (~100 tokens) on claude-sonnet-4-6...", (148, 163, 184)),
        ("Calculated pre-execution cost: $0.009891 USD", (251, 191, 36)),
        ("", (0, 0, 0)),
        ("🛡️  [CIRCUIT BREAKER TRIPPED BEFORE EXECUTION!]", (239, 68, 68)),
        ("   Reason         : cost_budget_exceeded", (239, 68, 68)),
        ("   Estimated Cost : $0.009891 USD", (251, 191, 36)),
        ("   Budget Cap     : $0.000001 USD", (148, 163, 184)),
        ("   Excess Blocked : $0.009890 USD", (239, 68, 68)),
        ("", (0, 0, 0)),
        ("✓ ZERO HTTP requests dispatched to OpenAny", (52, 211, 153)),
        ("✓ ZERO prepaid developer credits consumed", (52, 211, 153)),
        ("✓ Concurrency safe: budget reservations protect parallel workers", (96, 165, 250)),
    ]
    draw_terminal_window(img3, 24, 120, 830, 530, "bash — TrajectoryCircuitBreaker Defense", term3)
    hud3 = [
        ("CIRCUIT BREAKER", "TRIPPED (PRE-FLIGHT)", (239, 68, 68)),
        ("BLOCKED DISPATCH", "100% BLOCKED", (239, 68, 68)),
        ("CREDITS PRESERVED", "$0.009890 USD", (52, 211, 153)),
        ("NETWORK TRANSFERS", "0 bytes sent", (52, 211, 153)),
        ("RACE CONDITION SHIELD", "Thread-Safe Active", (56, 189, 248)),
    ]
    draw_hud_box(img3, 870, 120, 386, 530, "Cost Circuit Breaker HUD", hud3)
    scenes.append((img3, 240))

    # -----------------------------------------------------------------------
    # SCENE 4: Runaway Loop Interruption (8 seconds = 192 frames)
    # -----------------------------------------------------------------------
    img4 = create_base_canvas("04: Runaway Agent Loop Interruption", "Halting Infinite Retry Storms & Ping-Pong Oscillations")
    term4 = [
        ("Running autonomous agent loop on OpenAny...", (148, 163, 184)),
        ("Step 0: Invoked model openany:MiniMax-M2.5 (args: 'retry query') -> status=ok", (203, 213, 225)),
        ("Step 1: Invoked model openany:MiniMax-M2.5 (args: 'retry query') -> status=ok", (203, 213, 225)),
        ("Step 2: Attempting 3rd identical repeat...", (148, 163, 184)),
        ("", (0, 0, 0)),
        ("🛡️  [CIRCUIT BREAKER TRIPPED: exact_call_loop]", (239, 68, 68)),
        ("   Step Index     : 2", (203, 213, 225)),
        ("   Actor          : openany:MiniMax-M2.5", (251, 191, 36)),
        ("   Pathology      : Exact call repeated 3 times with identical arguments", (239, 68, 68)),
        ("   Action Taken   : Agent thread halted cleanly", (52, 211, 153)),
        ("", (0, 0, 0)),
        ("✓ Loop interrupted before runaway credit exhaustion", (52, 211, 153)),
        ("✓ Ping-pong cycles (A -> B -> A -> B) also protected", (96, 165, 250)),
    ]
    draw_terminal_window(img4, 24, 120, 830, 530, "bash — Loop & Oscillation Guard", term4)
    hud4 = [
        ("GUARD STATUS", "TRIPPED AT STEP 2", (239, 68, 68)),
        ("PATHOLOGY", "exact_call_loop", (239, 68, 68)),
        ("PING-PONG CHECK", "2-step & 3-step", (251, 191, 36)),
        ("STATE PRESERVATION", "Saved to Cassette", (56, 189, 248)),
    ]
    draw_hud_box(img4, 870, 120, 386, 530, "Loop Detector HUD", hud4)
    scenes.append((img4, 192))

    # -----------------------------------------------------------------------
    # SCENE 5: Tamper-Evident Cassette & 0.08 μs Replay (9 seconds = 216 frames)
    # -----------------------------------------------------------------------
    img5 = create_base_canvas("05: Cassette & Sub-Microsecond Replay", "Deterministic $0.00 CI/CD Testing via CassetteReplayer")
    term5 = [
        ("$ agentflight openany replay --cassette session.flight.json", (255, 255, 255)),
        ("Loading cryptographic flight cassette: session.flight.json", (148, 163, 184)),
        ("Verified SHA-256 Hash Chain: 48c8c8a71ea94eae0029372af6bcd6f2b6...", (52, 211, 153)),
        ("Replaying 50 recorded spans in offline sandbox...", (148, 163, 184)),
        ("", (0, 0, 0)),
        ("  Step 0: [llm_turn]  openany:MiniMax-M2.5  -> status=ok (Cost: $0.000030)", (203, 213, 225)),
        ("  Step 1: [tool_call] openany:mcp:lookup    -> status=ok (Cost: $0.000000)", (203, 213, 225)),
        ("  Step 2: [llm_turn]  openany:MiniMax-M2.5  -> status=ok (Cost: $0.000030)", (203, 213, 225)),
        ("  ... (47 remaining steps replayed deterministically)", (148, 163, 184)),
        ("", (0, 0, 0)),
        ("===================================================================", (71, 85, 105)),
        ("BENCHMARK RESULTS: P50 Replay Latency: 0.083 μs per span", (52, 211, 153)),
        ("THROUGHPUT       : 11,276,474 spans / second", (52, 211, 153)),
        ("EXTERNAL NETWORK : 0 calls ($0.00 testing spend)", (56, 189, 248)),
        ("===================================================================", (71, 85, 105)),
    ]
    draw_terminal_window(img5, 24, 120, 830, 530, "bash — agentflight openany replay", term5)
    hud5 = [
        ("REPLAY P50 LATENCY", "0.083 μs / span", (52, 211, 153)),
        ("REPLAY THROUGHPUT", "11.2 Million/sec", (52, 211, 153)),
        ("NETWORK DEPENDENCY", "Zero (100% Offline)", (56, 189, 248)),
        ("TESTING COST", "$0.00 USD", (52, 211, 153)),
        ("HASH INTEGRITY", "SHA-256 Validated", (251, 191, 36)),
    ]
    draw_hud_box(img5, 870, 120, 386, 530, "Replay Engine HUD", hud5)
    scenes.append((img5, 216))

    # -----------------------------------------------------------------------
    # SCENE 6: Remote MCP Tool-Smell Linter (7 seconds = 168 frames)
    # -----------------------------------------------------------------------
    img6 = create_base_canvas("06: Remote MCP Tool Ergonomics", "Auditing 50 OpenAny Tools Against Rules TS001-TS010")
    term6 = [
        ("$ agentflight openany lint-tools", (255, 255, 255)),
        ("Querying remote MCP server: https://mcp.openany.si/mcp...", (148, 163, 184)),
        ("Discovered 50 tools (Raw schema token footprint: 28,646 tokens / turn)", (251, 191, 36)),
        ("", (0, 0, 0)),
        ("AUDIT RESULTS: 151 Ergonomics Findings Detected", (239, 68, 68)),
        ("  • TS008 (Untyped property schemas)    : 83 errors", (239, 68, 68)),
        ("  • TS002 (Missing descriptions)        : 22 warnings", (251, 191, 36)),
        ("  • TS007 (Missing required array)      : 16 warnings", (251, 191, 36)),
        ("  • TS009 (Redundant empty wrappers)    : 16 warnings", (251, 191, 36)),
        ("  • TS004 (Excessive name length)       : 10 warnings", (203, 213, 225)),
        ("  • TS003 (Nesting depth > 3 levels)    : 4 warnings", (203, 213, 225)),
        ("", (0, 0, 0)),
        ("✓ agentflight compile prunes schemas by up to 78% context savings!", (52, 211, 153)),
    ]
    draw_terminal_window(img6, 24, 120, 830, 530, "bash — agentflight openany lint-tools", term6)
    hud6 = [
        ("MCP SERVER", "mcp.openany.si/mcp", (56, 189, 248)),
        ("TOOLS AUDITED", "50 Remote APIs", (203, 213, 225)),
        ("RAW TOKENS/TURN", "28,646 tokens", (239, 68, 68)),
        ("COMPILED SAVINGS", "Up to 78% Context", (52, 211, 153)),
    ]
    draw_hud_box(img6, 870, 120, 386, 530, "MCP Linter HUD", hud6)
    scenes.append((img6, 168))

    # -----------------------------------------------------------------------
    # SCENE 7: Outro / Commercial Launch Card (7 seconds = 168 frames)
    # -----------------------------------------------------------------------
    img7 = create_base_canvas("Commercial Launch Ready", "AgentFlight v1.2.0 × OpenAny Partnership")
    d7 = ImageDraw.Draw(img7)
    d7.rounded_rectangle([(160, 140), (1120, 580)], radius=16, fill=(10, 15, 30), outline=(16, 185, 129), width=2)
    d7.text((220, 180), "AgentFlight v1.2.0", font=FONT_BIG, fill=(255, 255, 255))
    d7.text((220, 235), "The Black-Box Flight Recorder and Cost Control Plane for AI Agents", font=FONT_SUB, fill=(52, 211, 153))

    d7.text((220, 290), "COMMERCIAL HIGHLIGHTS:", font=FONT_MONO_BOLD, fill=(251, 191, 36))
    d7.text((220, 320), "✔ Confirmed 30% Permanent Revenue Share on Attributed Usage\n✔ Outbound Header: X-OpenAny-Partner-Id: agentflight\n✔ Pre-Execution Cost Circuit Breakers (Zero-Credit Defense)\n✔ 0.08 μs Sub-Microsecond Offline Replay ($0.00 CI Testing)\n✔ 132/132 Tests Passed with Zero Regressions", font=FONT_MONO, fill=(203, 213, 225))

    d7.rounded_rectangle([(220, 460), (1060, 530)], radius=8, fill=(15, 23, 42), outline=(59, 130, 246), width=1)
    d7.text((240, 475), "GET STARTED IN YOUR TERMINAL:", font=FONT_MONO_SM, fill=(148, 163, 184))
    d7.text((240, 495), "$ pip install agentflight  &&  agentflight openany models", font=FONT_MONO_BOLD, fill=(56, 189, 248))

    d7.text((220, 550), "Owner: Akandwanaho Ivan Alvin  |  Portal: https://agentflight-tau.vercel.app", font=FONT_MONO_SM, fill=(148, 163, 184))
    scenes.append((img7, 168))

    return scenes


def main() -> int:
    out_dir = "marketing/openany-launch"
    os.makedirs(out_dir, exist_ok=True)
    mp4_path = os.path.join(out_dir, "agentflight_openany_demo.mp4")
    gif_path = os.path.join(out_dir, "agentflight_openany_demo.gif")

    print(f"🎬 Generating AgentFlight × OpenAny Demonstration Video ({WIDTH}x{HEIGHT} @ {FPS}fps)...")
    scenes = render_all_scenes()
    total_frames = sum(ticks for _, ticks in scenes)
    duration_sec = total_frames / FPS
    print(f"Total scenes: {len(scenes)} | Total frames: {total_frames:,} ({duration_sec:.1f} seconds)")

    # 1. Write MP4 using hardware-accelerated imageio-ffmpeg
    print(f"\n[1/2] Encoding MP4 video to {mp4_path}...")
    writer = imageio_ffmpeg.write_frames(
        mp4_path,
        (WIDTH, HEIGHT),
        fps=FPS,
        codec="libx264",
        pix_fmt_in="rgb24",
        output_params=["-preset", "fast", "-crf", "22"],
    )
    writer.send(None)  # prime generator

    frame_count = 0
    t0 = time.perf_counter()
    sample_gif_frames = []

    for idx, (img, ticks) in enumerate(scenes):
        frame_bytes = np.array(img).tobytes()
        for _ in range(ticks):
            writer.send(frame_bytes)
            frame_count += 1
        # Collect 1 frame per scene for lightweight GIF preview
        sample_gif_frames.append(img.resize((640, 360), Image.Resampling.LANCZOS))
        print(f"  • Encoded Scene {idx}: {ticks} frames ({frame_count}/{total_frames})")

    writer.close()
    encode_time = time.perf_counter() - t0
    mp4_size_mb = os.path.getsize(mp4_path) / (1024 * 1024)
    print(f"✓ MP4 generation complete in {encode_time:.2f}s! File size: {mp4_size_mb:.2f} MB")

    # 2. Write animated GIF preview
    print(f"\n[2/2] Generating animated GIF preview to {gif_path}...")
    if sample_gif_frames:
        sample_gif_frames[0].save(
            gif_path,
            save_all=True,
            append_images=sample_gif_frames[1:],
            duration=3000,
            loop=0,
        )
        gif_size_mb = os.path.getsize(gif_path) / (1024 * 1024)
        print(f"✓ GIF preview complete! File size: {gif_size_mb:.2f} MB")

    print("\n" + "=" * 70)
    print("  🚀 DEMO VIDEO GENERATION SUCCESSFUL")
    print("=" * 70)
    print(f"• MP4 Video File  : {mp4_path}")
    print(f"• GIF Preview File: {gif_path}")
    print(f"• Resolution      : {WIDTH}x{HEIGHT} (720p HD @ 24fps)")
    print(f"• Duration        : {duration_sec:.1f} seconds")
    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
