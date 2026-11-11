#!/usr/bin/env python3
"""
scripts.render_makeover_video
=============================
Produces a cinematic, studio-grade makeover demonstration video of the
AgentFlight × OpenAny commercial integration with:
- Synchronized voiceover narration (Mac audio synthesizer)
- Ambient sci-fi synthesizer score + UI sound effects
- Ken Burns 3D camera pan/zoom on cinematic mission control hero art
- Dynamic terminal character-by-character typing animations
- Real-time HUD telemetry, pulsing attribution badges & flashing circuit breaker shields
- Synchronized on-screen closed captions / subtitles

Outputs:
- marketing/openany-launch/agentflight_openany_makeover_demo.mp4 (Full 1080p/720p HD with AAC audio)
- marketing/openany-launch/agentflight_openany_demo.mp4 (Updated master)
- marketing/openany-launch/agentflight_openany_demo.gif (Updated GIF preview)
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
import time
import wave
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1280
HEIGHT = 720
FPS = 24
SAMPLE_RATE = 44100

# Typography
FONT_TITLE = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
FONT_SUB = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
FONT_MONO_BOLD = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 16)
FONT_MONO = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 14)
FONT_MONO_SM = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 12)
FONT_BIG = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38)
FONT_CAPTION = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)

HERO_ART_PATH = "marketing/openany-launch/cinematic_hero_thumbnail.jpg"


def get_hero_image() -> Image.Image:
    if os.path.exists(HERO_ART_PATH):
        try:
            im = Image.open(HERO_ART_PATH).convert("RGB")
            return im.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        except Exception:
            pass
    return Image.new("RGB", (WIDTH, HEIGHT), color=(6, 10, 20))


HERO_IMG = get_hero_image()


# ---------------------------------------------------------------------------
# Audio Production Engine (Voice + Ambient Synth + UI SFX)
# ---------------------------------------------------------------------------

SCENE_SCRIPTS = [
    ("scene_0", "What happens when the fastest AI flight recorder meets an open marketplace of 128 models and 3,200 APIs? Total reliability.", 10.5),
    ("scene_1", "With AgentFlight, connect to OpenAny in seconds. Discover models, inspect context windows, and query real-time per-token pricing directly from your terminal.", 11.5),
    ("scene_2", "Every request transmits our verified partner attribution header: X OpenAny Partner Id: agentflight. Powers a permanent 30 percent revenue share, while strictly isolating your credentials.", 13.0),
    ("scene_3", "Never burn through API credits on runaway calls again. AgentFlight’s pre-execution circuit breaker calculates costs before dispatch and halts expensive requests before they leave your machine.", 12.5),
    ("scene_4", "Recursive loops and ping-pong tool cycles are stopped at step two. Your spend is protected; your agents stay on course.", 8.0),
    ("scene_5", "Every step is recorded into a tamper-evident cryptographic cassette. Replay entire 50-step trajectories in your CI suite at 0.08 microseconds per span — completely offline, with zero network calls and zero cost.", 15.5),
    ("scene_6", "Audit OpenAny remote MCP tools against 10 ergonomics rules, trimming prompt schemas by up to 78 percent for maximum function-calling precision.", 10.5),
    ("scene_7", "AgentFlight: The black-box telemetry and cost control plane for the agentic web. Available now on PyPI and GitHub.", 8.5),
]


def build_master_audio(work_dir: str, ffmpeg_bin: str) -> str:
    """Generate voice segments, synthesize ambient sci-fi music & SFX, and mix master stereo WAV."""
    voice = "Daniel"
    rate = 180
    voice_wavs = []

    print("  [Audio] Generating speech synthesis with Daniel (en_GB)...")
    for name, text, target_dur in SCENE_SCRIPTS:
        aiff_p = os.path.join(work_dir, f"{name}.aiff")
        wav_p = os.path.join(work_dir, f"{name}.wav")
        padded_wav_p = os.path.join(work_dir, f"{name}_padded.wav")
        subprocess.run(["say", "-v", voice, "-r", str(rate), text, "-o", aiff_p], check=True)
        subprocess.run([ffmpeg_bin, "-y", "-i", aiff_p, "-ar", str(SAMPLE_RATE), "-ac", "2", wav_p], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Pad or trim to match exact target duration
        subprocess.run([
            ffmpeg_bin, "-y", "-i", wav_p,
            "-af", f"apad=whole_dur={target_dur}",
            "-t", str(target_dur),
            padded_wav_p
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        voice_wavs.append(padded_wav_p)

    # Concat padded voice clips
    concat_txt = os.path.join(work_dir, "concat.txt")
    with open(concat_txt, "w") as f:
        for p in voice_wavs:
            f.write(f"file '{p}'\n")

    voice_master = os.path.join(work_dir, "voice_master.wav")
    subprocess.run([ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", voice_master], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    total_duration = sum(d for _, _, d in SCENE_SCRIPTS)
    print(f"  [Audio] Master voice track assembled: {total_duration:.1f} seconds")

    # Synthesize Ambient Sci-Fi Synth Drone & UI SFX
    print("  [Audio] Synthesizing ambient sci-fi score & cybernetic UI sound effects...")
    t = np.linspace(0, total_duration, int(SAMPLE_RATE * total_duration), endpoint=False)
    bass = 0.07 * np.sin(2 * np.pi * 55 * t)
    mid = 0.05 * np.sin(2 * np.pi * 110 * t + 0.5)
    fifth = 0.04 * np.sin(2 * np.pi * 164.81 * t + 1.0)
    shimmer = 0.02 * np.sin(2 * np.pi * 220 * t + 0.2 * np.sin(2 * np.pi * 0.2 * t))
    env = np.ones_like(t)
    env[:int(SAMPLE_RATE * 2.0)] = np.linspace(0, 1, int(SAMPLE_RATE * 2.0))
    env[-int(SAMPLE_RATE * 3.0):] = np.linspace(1, 0, int(SAMPLE_RATE * 3.0))
    synth = (bass + mid + fifth + shimmer) * env

    # Add UI SFX
    sfx = np.zeros_like(t)
    def add_tone(start_s: float, freq: float, dur_s: float, vol: float = 0.15):
        idx = int(start_s * SAMPLE_RATE)
        n = int(dur_s * SAMPLE_RATE)
        if idx + n < len(sfx):
            st = np.linspace(0, dur_s, n, endpoint=False)
            sfx[idx:idx+n] += vol * np.sin(2 * np.pi * freq * st) * np.exp(-st * 8)

    add_tone(0.2, 587.33, 0.5, 0.12)
    add_tone(0.4, 880.0, 0.6, 0.10)
    add_tone(10.5, 1200.0, 0.1, 0.08)
    add_tone(22.0, 1046.5, 0.4, 0.15)  # Attribution lock ping
    add_tone(35.0, 220.0, 0.8, 0.25)   # Circuit breaker buzz
    add_tone(35.2, 330.0, 0.6, 0.20)
    add_tone(47.5, 440.0, 0.3, 0.12)
    add_tone(55.5, 1760.0, 0.4, 0.18)  # High speed replay swoosh
    add_tone(71.0, 880.0, 0.2, 0.12)
    add_tone(81.5, 1046.5, 0.8, 0.15)  # Outro chord

    music_mix = np.clip(synth + sfx, -0.9, 0.9)
    music_pcm = (music_mix * 32767).astype(np.int16)
    music_stereo = np.column_stack((music_pcm, music_pcm))
    music_path = os.path.join(work_dir, "music_master.wav")
    with wave.open(music_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(music_stereo.tobytes())

    # Final Mixed Master Audio via ffmpeg
    final_audio = os.path.join(work_dir, "mixed_audio.wav")
    subprocess.run([
        ffmpeg_bin, "-y",
        "-i", voice_master,
        "-i", music_path,
        "-filter_complex", "[0:a]volume=1.0[v];[1:a]volume=0.22[m];[v][m]amix=inputs=2:duration=longest",
        final_audio
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return final_audio


# ---------------------------------------------------------------------------
# Visual Composition & Animation Engine
# ---------------------------------------------------------------------------

def draw_top_and_bottom_bars(draw: ImageDraw.Draw, scene_title: str, subheader: str = ""):
    # Header
    draw.rectangle([(0, 0), (WIDTH, 56)], fill=(12, 18, 34))
    draw.line([(0, 56), (WIDTH, 56)], fill=(30, 41, 59), width=1)
    draw.text((24, 14), "✈️  AGENTFLIGHT × OPENANY", font=FONT_TITLE, fill=(255, 255, 255))
    draw.text((430, 22), "COMMERCIAL LAUNCH DEMO", font=FONT_MONO_SM, fill=(148, 163, 184))

    # Pulsing Pill
    draw.rounded_rectangle([(780, 12), (1030, 44)], radius=6, fill=(16, 24, 48), outline=(0, 71, 255), width=1)
    draw.text((792, 21), "X-OpenAny-Partner-Id: agentflight", font=FONT_MONO_SM, fill=(96, 165, 250))

    # Revenue Share Pill
    draw.rounded_rectangle([(1045, 12), (1256, 44)], radius=6, fill=(16, 36, 28), outline=(16, 185, 129), width=1)
    draw.text((1058, 21), "30% PERMANENT REV SHARE", font=FONT_MONO_SM, fill=(52, 211, 153))

    # Sub-header
    draw.rectangle([(24, 66), (1256, 100)], fill=(15, 23, 42))
    draw.text((36, 74), f"STAGE: {scene_title.upper()}", font=FONT_MONO_BOLD, fill=(245, 158, 11))
    if subheader:
        draw.text((380, 76), subheader, font=FONT_MONO_SM, fill=(148, 163, 184))

    # Footer
    draw.rectangle([(0, HEIGHT - 36), (WIDTH, HEIGHT)], fill=(10, 15, 28))
    draw.line([(0, HEIGHT - 36), (WIDTH, HEIGHT - 36)], fill=(30, 41, 59), width=1)
    draw.text((24, HEIGHT - 26), "Creator & Owner: Akandwanaho Ivan Alvin • Partner: OpenAny (Pistis) • MIT License", font=FONT_MONO_SM, fill=(100, 116, 139))
    draw.text((1080, HEIGHT - 26), "https://openany.si", font=FONT_MONO_SM, fill=(56, 189, 248))


def draw_subtitle_bar(draw: ImageDraw.Draw, text: str):
    """Render high-contrast closed caption subtitle at the bottom center."""
    draw.rounded_rectangle([(80, HEIGHT - 84), (WIDTH - 80, HEIGHT - 46)], radius=6, fill=(0, 0, 0, 220), outline=(59, 130, 246), width=1)
    # Highlight keywords
    draw.text((WIDTH // 2, HEIGHT - 66), text, font=FONT_CAPTION, fill=(255, 255, 255), anchor="mm")


def render_scene_0_frame(frame_idx: int, total_frames: int) -> Image.Image:
    """Scene 0: Ken Burns zoom on cinematic 3D hero art + glassmorphic title card."""
    progress = frame_idx / max(1, total_frames)
    # Slow subtle zoom from 1.0 to 1.06
    scale = 1.0 + 0.06 * progress
    w_crop = int(WIDTH / scale)
    h_crop = int(HEIGHT / scale)
    x1 = (WIDTH - w_crop) // 2
    y1 = (HEIGHT - h_crop) // 2
    cropped = HERO_IMG.crop((x1, y1, x1 + w_crop, y1 + h_crop))
    img = cropped.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)

    # Dark overlay for readability
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 120))
    img.paste(overlay, (0, 0), overlay)
    draw = ImageDraw.Draw(img)

    # Glassmorphism Center Card
    draw.rounded_rectangle([(140, 120), (1140, 560)], radius=16, fill=(10, 16, 32), outline=(0, 71, 255), width=2)
    draw.text((180, 150), "AgentFlight × OpenAny", font=FONT_BIG, fill=(255, 255, 255))
    draw.text((180, 205), "Autonomous AI Flight Recorder meets 128+ Multi-Model Marketplace", font=FONT_SUB, fill=(203, 213, 225))

    # 3 Cards
    draw.rounded_rectangle([(180, 245), (460, 460)], radius=10, fill=(15, 23, 42), outline=(59, 130, 246), width=1)
    draw.text((196, 260), "01 / COMMERCIAL SHARE", font=FONT_MONO_BOLD, fill=(96, 165, 250))
    draw.text((196, 290), "• 30% Permanent Revenue\n• Header: X-OpenAny-Partner-Id\n• Verified Backend Ledger\n• Lifetime Partner Attribution", font=FONT_MONO_SM, fill=(203, 213, 225))

    draw.rounded_rectangle([(490, 245), (770, 460)], radius=10, fill=(15, 23, 42), outline=(245, 158, 11), width=1)
    draw.text((506, 260), "02 / ZERO-CREDIT SHIELD", font=FONT_MONO_BOLD, fill=(251, 191, 36))
    draw.text((506, 290), "• Pre-execution circuit breaker\n• Halts unaffordable requests\n• Thread-safe reservations\n• $0.00 spent on trip", font=FONT_MONO_SM, fill=(203, 213, 225))

    draw.rounded_rectangle([(800, 245), (1080, 460)], radius=10, fill=(15, 23, 42), outline=(16, 185, 129), width=1)
    draw.text((816, 260), "03 / 0.08 μs REPLAY", font=FONT_MONO_BOLD, fill=(52, 211, 153))
    draw.text((816, 290), "• Cryptographic .flight.json\n• SHA-256 hash chaining\n• 11.2M+ spans/sec replay\n• $0.00 offline CI testing", font=FONT_MONO_SM, fill=(203, 213, 225))

    draw.text((180, 500), "Creator & Owner: Akandwanaho Ivan Alvin  •  Commercial Partner: OpenAny (Pistis)", font=FONT_MONO_SM, fill=(148, 163, 184))

    draw_top_and_bottom_bars(draw, "00: Aerospace Mission Control", "Official Commercial Architecture (v1.2.0)")
    draw_subtitle_bar(draw, "What happens when the fastest AI flight recorder meets an open marketplace of 128 models? Total reliability.")
    return img


def render_scene_1_frame(frame_idx: int, total_frames: int) -> Image.Image:
    """Scene 1: Interactive Model Fleet Discovery."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(7, 10, 19))
    draw = ImageDraw.Draw(img)

    # Typing effect for CLI command
    cmd_text = "agentflight openany models"
    chars_to_show = min(len(cmd_text), int((frame_idx / 24.0) * len(cmd_text) * 1.5))
    cursor = "_" if (frame_idx // 12) % 2 == 0 else " "
    typed = cmd_text[:chars_to_show] + cursor

    # Terminal Lines
    lines = [
        (f"$ {typed}", (255, 255, 255)),
    ]
    if frame_idx > 30:
        lines.append(("Connecting to OpenAny Gateway (https://api.openany.si/v1/models)...", (148, 163, 184)))
    if frame_idx > 50:
        lines.append(("✓ Discovered 128 production models available:", (52, 211, 153)))
        lines.append(("-------------------------------------------------------------------", (71, 85, 105)))
        lines.append(("  Model ID                Context      Prompt $/1M    Completion $/1M", (148, 163, 184)))
        lines.append(("-------------------------------------------------------------------", (71, 85, 105)))
    if frame_idx > 70:
        lines.append(("  MiniMax-M2.5            200,000      $0.3000        $1.2000", (251, 191, 36)))
        lines.append(("  claude-sonnet-4-6     1,000,000      $3.0000       $15.0000", (96, 165, 250)))
    if frame_idx > 90:
        lines.append(("  DeepSeek-R1 (Reasoning) 128,000      $0.5500        $2.1900", (52, 211, 153)))
        lines.append(("  Qwen-2.5-Coder-32B      128,000      $0.2000        $0.2000", (203, 213, 225)))
        lines.append(("  Midjourney-v8.1         Image Gen    —              $1.4290", (244, 114, 182)))
        lines.append(("  ... and 123 more models in OpenAny live catalog", (148, 163, 184)))

    # Terminal box
    draw.rounded_rectangle([(24, 110), (850, 620)], radius=8, fill=(4, 6, 12), outline=(30, 41, 59), width=1)
    draw.rounded_rectangle([(24, 110), (850, 140)], radius=8, fill=(15, 23, 42))
    draw.ellipse([(36, 120), (46, 130)], fill=(239, 68, 68))
    draw.ellipse([(52, 120), (62, 130)], fill=(245, 158, 11))
    draw.ellipse([(68, 120), (78, 130)], fill=(16, 185, 129))
    draw.text((94, 118), "bash — agentflight openany models", font=FONT_MONO_SM, fill=(148, 163, 184))

    cy = 152
    for l_text, col in lines:
        draw.text((40, cy), l_text, font=FONT_MONO, fill=col)
        cy += 24

    # HUD Box
    hud_x = 874
    draw.rounded_rectangle([(hud_x, 110), (1256, 620)], radius=8, fill=(10, 16, 32), outline=(0, 71, 255), width=1)
    draw.rounded_rectangle([(hud_x, 110), (1256, 140)], fill=(16, 24, 48))
    draw.text((hud_x + 16, 118), "OPENANY FLEET METRICS", font=FONT_MONO_BOLD, fill=(96, 165, 250))

    hud_items = [
        ("GATEWAY ENDPOINT", "api.openany.si/v1", (56, 189, 248)),
        ("ACTIVE FLEET", "128 Verified Models", (52, 211, 153)),
        ("MAX CONTEXT", "1,000,000 tokens", (251, 191, 36)),
        ("API AUTH", "Bearer ale-P4...7ydY", (203, 213, 225)),
        ("PARTNER HEADER", "X-OpenAny-Partner-Id", (96, 165, 250)),
    ]
    hy = 160
    for lbl, val, col in hud_items:
        draw.text((hud_x + 16, hy), lbl, font=FONT_MONO_SM, fill=(148, 163, 184))
        draw.text((hud_x + 16, hy + 18), val, font=FONT_MONO_BOLD, fill=col)
        hy += 52

    draw_top_and_bottom_bars(draw, "01: Multi-Model Discovery", "128 Models Verified at api.openany.si/v1")
    draw_subtitle_bar(draw, "With AgentFlight, connect to OpenAny in seconds. Query models, context windows, and real-time per-token pricing.")
    return img


def render_scene_2_frame(frame_idx: int, total_frames: int) -> Image.Image:
    """Scene 2: Outbound HTTP Header Attribution & Live Execution."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(7, 10, 19))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([(24, 110), (850, 620)], radius=8, fill=(4, 6, 12), outline=(30, 41, 59), width=1)
    draw.rounded_rectangle([(24, 110), (850, 140)], radius=8, fill=(15, 23, 42))
    draw.text((40, 118), "HTTP/1.1 Packet Inspector — api.openany.si", font=FONT_MONO_SM, fill=(148, 163, 184))

    # Pulsing highlight for attribution header
    pulse = 180 + int(70 * math.sin(frame_idx * 0.2))
    hdr_color = (pulse, 255, pulse)

    lines = [
        ("$ agentflight openany chat --model MiniMax-M2.5", (255, 255, 255)),
        (">>> OUTBOUND HTTP POST REQUEST DISPATCHED:", (96, 165, 250)),
        ("    POST /v1/chat/completions HTTP/1.1", (203, 213, 225)),
        ("    Host: api.openany.si", (148, 163, 184)),
        ("    Authorization: Bearer ale-P4...7ydY", (148, 163, 184)),
        ("    X-OpenAny-Partner-Id: agentflight  <-- [VERIFIED 30% REVENUE SHARE]", hdr_color),
        ("    User-Agent: agentflight/1.2.0 (partner=openany)", (148, 163, 184)),
        ("", (0, 0, 0)),
        ("<<< HTTP 200 OK (Latency: 1,767.89 ms)", (52, 211, 153)),
        ("Response ID: 0743400fadffb4e5fa37eacbe28eb0fa", (203, 213, 225)),
        ("Assistant: 'An AI flight recorder captures non-deterministic steps...'", (255, 255, 255)),
        ("Tokens: 60 total (52 prompt + 8 completion) | Spend: $0.000025 USD", (251, 191, 36)),
        ("✓ Flight recorded: tests/cassettes/openany_live_attribution.flight.json", (52, 211, 153)),
    ]

    cy = 152
    for l_text, col in lines:
        draw.text((40, cy), l_text, font=FONT_MONO, fill=col)
        cy += 24

    hud_x = 874
    draw.rounded_rectangle([(hud_x, 110), (1256, 620)], radius=8, fill=(10, 16, 32), outline=(16, 185, 129), width=1)
    draw.rounded_rectangle([(hud_x, 110), (1256, 140)], fill=(16, 36, 28))
    draw.text((hud_x + 16, 118), "LIVE ATTRIBUTION TELEMETRY", font=FONT_MONO_BOLD, fill=(52, 211, 153))

    hud_items = [
        ("PARTNER HEADER", "X-OpenAny-Partner-Id", (52, 211, 153)),
        ("REQUEST ID", "0743400fadffb4e...", (203, 213, 225)),
        ("MODEL", "MiniMax-M2.5", (251, 191, 36)),
        ("ROUNDTRIP TIME", "1,767 ms", (56, 189, 248)),
        ("BILLED SPEND", "$0.000025 USD", (52, 211, 153)),
        ("REVENUE SHARE", "30% Permanent Lifetime", (96, 165, 250)),
    ]
    hy = 160
    for lbl, val, col in hud_items:
        draw.text((hud_x + 16, hy), lbl, font=FONT_MONO_SM, fill=(148, 163, 184))
        draw.text((hud_x + 16, hy + 18), val, font=FONT_MONO_BOLD, fill=col)
        hy += 52

    draw_top_and_bottom_bars(draw, "02: Live Execution & Verified Attribution", "Attribution Header: X-OpenAny-Partner-Id: agentflight")
    draw_subtitle_bar(draw, "Every request transmits our verified partner header: X-OpenAny-Partner-Id. Powers a permanent 30% revenue share.")
    return img


def render_scene_3_frame(frame_idx: int, total_frames: int) -> Image.Image:
    """Scene 3: Pre-Execution Budget Defense (Flashing Holographic Shield)."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(7, 10, 19))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([(24, 110), (850, 620)], radius=8, fill=(4, 6, 12), outline=(30, 41, 59), width=1)
    draw.rounded_rectangle([(24, 110), (850, 140)], radius=8, fill=(15, 23, 42))
    draw.text((40, 118), "bash — TrajectoryCircuitBreaker Defense", font=FONT_MONO_SM, fill=(148, 163, 184))

    # Flashing Alert box
    flash_on = (frame_idx // 8) % 2 == 0
    alert_fill = (50, 15, 15) if flash_on else (25, 8, 8)
    draw.rounded_rectangle([(40, 240), (830, 420)], radius=8, fill=alert_fill, outline=(239, 68, 68), width=2)
    draw.text((60, 260), "🛡️  [CIRCUIT BREAKER TRIPPED BEFORE EXECUTION!]", font=FONT_MONO_BOLD, fill=(239, 68, 68))
    draw.text((60, 290), "Reason         : cost_budget_exceeded\nEstimated Cost : $0.009891 USD\nBudget Cap     : $0.000001 USD\nExcess Blocked : $0.009890 USD", font=FONT_MONO, fill=(251, 191, 36))
    draw.text((60, 385), "✓ ZERO HTTP requests dispatched  |  ✓ $0.00 prepaid credits consumed", font=FONT_MONO_BOLD, fill=(52, 211, 153))

    lines = [
        ("$ agentflight openany chat --model claude-sonnet-4-6 --budget 0.000001", (255, 255, 255)),
        ("Developer set strict budget limit: $0.000001 USD", (148, 163, 184)),
        ("Evaluating prompt tokens on claude-sonnet-4-6 ($3.00/1M prompt)...", (148, 163, 184)),
    ]
    cy = 152
    for l_text, col in lines:
        draw.text((40, cy), l_text, font=FONT_MONO, fill=col)
        cy += 24

    hud_x = 874
    draw.rounded_rectangle([(hud_x, 110), (1256, 620)], radius=8, fill=(16, 10, 14), outline=(239, 68, 68), width=1)
    draw.rounded_rectangle([(hud_x, 110), (1256, 140)], fill=(36, 12, 16))
    draw.text((hud_x + 16, 118), "CIRCUIT BREAKER SHIELD", font=FONT_MONO_BOLD, fill=(239, 68, 68))

    hud_items = [
        ("BREAKER STATE", "TRIPPED (PRE-FLIGHT)", (239, 68, 68)),
        ("PROTECTED FUNDS", "$0.009890 USD", (52, 211, 153)),
        ("EGRESS PACKETS", "0 bytes dispatched", (52, 211, 153)),
        ("CONCURRENCY GUARD", "Thread-Safe Reservation", (56, 189, 248)),
    ]
    hy = 160
    for lbl, val, col in hud_items:
        draw.text((hud_x + 16, hy), lbl, font=FONT_MONO_SM, fill=(148, 163, 184))
        draw.text((hud_x + 16, hy + 18), val, font=FONT_MONO_BOLD, fill=col)
        hy += 52

    draw_top_and_bottom_bars(draw, "03: Pre-Execution Budget Defense", "Calculates Costs Before Dispatch — Halts Unaffordable Calls")
    draw_subtitle_bar(draw, "Never burn credits on runaway calls again. Pre-execution circuit breakers halt expensive requests before they leave your machine.")
    return img


def render_scene_4_frame(frame_idx: int, total_frames: int) -> Image.Image:
    """Scene 4: Runaway Loop Interruption."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(7, 10, 19))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([(24, 110), (850, 620)], radius=8, fill=(4, 6, 12), outline=(30, 41, 59), width=1)
    draw.rounded_rectangle([(24, 110), (850, 140)], radius=8, fill=(15, 23, 42))
    draw.text((40, 118), "Loop & Oscillation Detection Engine", font=FONT_MONO_SM, fill=(148, 163, 184))

    lines = [
        ("Simulating autonomous agent trapped in retry loop...", (148, 163, 184)),
        ("Step 0: openany:MiniMax-M2.5 (args: 'retry query') -> ok", (203, 213, 225)),
        ("Step 1: openany:MiniMax-M2.5 (args: 'retry query') -> ok", (203, 213, 225)),
        ("Step 2: 3rd identical invocation detected...", (148, 163, 184)),
        ("", (0, 0, 0)),
        ("🛡️  [LOOP INTERRUPTED AT STEP 2: exact_call_loop]", (239, 68, 68)),
        ("   Actor      : openany:MiniMax-M2.5", (251, 191, 36)),
        ("   Pathology  : Exact call repeated 3 times with identical arguments", (239, 68, 68)),
        ("   Mitigation : Agent execution halted cleanly before credit burn", (52, 211, 153)),
        ("", (0, 0, 0)),
        ("✓ Ping-pong cycles (A -> B -> A -> B) also protected", (96, 165, 250)),
    ]
    cy = 152
    for l_text, col in lines:
        draw.text((40, cy), l_text, font=FONT_MONO, fill=col)
        cy += 24

    hud_x = 874
    draw.rounded_rectangle([(hud_x, 110), (1256, 620)], radius=8, fill=(16, 12, 10), outline=(245, 158, 11), width=1)
    draw.rounded_rectangle([(hud_x, 110), (1256, 140)], fill=(36, 24, 12))
    draw.text((hud_x + 16, 118), "LOOP GUARD HUD", font=FONT_MONO_BOLD, fill=(245, 158, 11))

    hud_items = [
        ("STATUS", "HALTED AT STEP 2", (239, 68, 68)),
        ("REASON", "exact_call_loop", (245, 158, 11)),
        ("CYCLES CHECKED", "2-step & 3-step", (203, 213, 225)),
        ("CREDITS SAVED", "Runaway spend avoided", (52, 211, 153)),
    ]
    hy = 160
    for lbl, val, col in hud_items:
        draw.text((hud_x + 16, hy), lbl, font=FONT_MONO_SM, fill=(148, 163, 184))
        draw.text((hud_x + 16, hy + 18), val, font=FONT_MONO_BOLD, fill=col)
        hy += 52

    draw_top_and_bottom_bars(draw, "04: Runaway Loop Interruption", "Halts Cyclic Oscillations & Consecutive Error Storms")
    draw_subtitle_bar(draw, "Recursive loops and ping-pong tool cycles are stopped at step two. Your spend is protected; your agents stay on course.")
    return img


def render_scene_5_frame(frame_idx: int, total_frames: int) -> Image.Image:
    """Scene 5: Cassette & Sub-Microsecond Offline Replay."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(7, 10, 19))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([(24, 110), (850, 620)], radius=8, fill=(4, 6, 12), outline=(30, 41, 59), width=1)
    draw.rounded_rectangle([(24, 110), (850, 140)], radius=8, fill=(15, 23, 42))
    draw.text((40, 118), "bash — agentflight openany replay", font=FONT_MONO_SM, fill=(148, 163, 184))

    # Fast progress bar
    prog = min(1.0, (frame_idx / 40.0))
    bar_w = int(prog * 750)
    draw.rectangle([(40, 200), (40 + bar_w, 208)], fill=(16, 185, 129))

    lines = [
        ("$ agentflight openany replay --cassette session.flight.json", (255, 255, 255)),
        ("Loading cryptographic flight cassette: session.flight.json", (148, 163, 184)),
        ("", (0, 0, 0)),
        ("Verified SHA-256 Hash Chain: 48c8c8a71ea94eae0029372af6bcd6f2b6...", (52, 211, 153)),
        ("Replaying 50 recorded spans in offline sandbox...", (148, 163, 184)),
        ("  Step 0: [llm_turn]  openany:MiniMax-M2.5  -> status=ok ($0.000030)", (203, 213, 225)),
        ("  Step 1: [tool_call] openany:mcp:lookup    -> status=ok ($0.000000)", (203, 213, 225)),
        ("  ... (48 steps replayed deterministically in memory)", (148, 163, 184)),
        ("", (0, 0, 0)),
        ("BENCHMARK RESULTS:", (56, 189, 248)),
        ("  P50 Replay Latency : 0.083 μs per span", (52, 211, 153)),
        ("  Throughput         : 11,276,474 spans / second", (52, 211, 153)),
        ("  External Network   : 0 calls ($0.00 testing spend)", (52, 211, 153)),
    ]
    cy = 152
    for l_text, col in lines:
        draw.text((40, cy), l_text, font=FONT_MONO, fill=col)
        cy += 24

    hud_x = 874
    draw.rounded_rectangle([(hud_x, 110), (1256, 620)], radius=8, fill=(10, 24, 18), outline=(16, 185, 129), width=1)
    draw.rounded_rectangle([(hud_x, 110), (1256, 140)], fill=(16, 36, 28))
    draw.text((hud_x + 16, 118), "REPLAY BENCHMARK HUD", font=FONT_MONO_BOLD, fill=(52, 211, 153))

    hud_items = [
        ("P50 LATENCY", "0.083 μs / span", (52, 211, 153)),
        ("THROUGHPUT", "11.2 Million / sec", (52, 211, 153)),
        ("EXTERNAL NETWORK", "Zero (100% Offline)", (56, 189, 248)),
        ("CI TESTING COST", "$0.00 USD", (52, 211, 153)),
        ("CRYPTOGRAPHIC CHAIN", "SHA-256 Validated", (251, 191, 36)),
    ]
    hy = 160
    for lbl, val, col in hud_items:
        draw.text((hud_x + 16, hy), lbl, font=FONT_MONO_SM, fill=(148, 163, 184))
        draw.text((hud_x + 16, hy + 18), val, font=FONT_MONO_BOLD, fill=col)
        hy += 52

    draw_top_and_bottom_bars(draw, "05: Cassette & 0.08 μs Offline Replay", "Deterministic $0.00 CI/CD Testing via CassetteReplayer")
    draw_subtitle_bar(draw, "Replay entire 50-step trajectories in your CI suite at 0.08 microseconds per span — completely offline, zero cost.")
    return img


def render_scene_6_frame(frame_idx: int, total_frames: int) -> Image.Image:
    """Scene 6: Remote MCP Tool Ergonomics Linter."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(7, 10, 19))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([(24, 110), (850, 620)], radius=8, fill=(4, 6, 12), outline=(30, 41, 59), width=1)
    draw.rounded_rectangle([(24, 110), (850, 140)], radius=8, fill=(15, 23, 42))
    draw.text((40, 118), "bash — agentflight openany lint-tools", font=FONT_MONO_SM, fill=(148, 163, 184))

    lines = [
        ("$ agentflight openany lint-tools", (255, 255, 255)),
        ("Auditing OpenAny remote MCP tools (https://mcp.openany.si/mcp)...", (148, 163, 184)),
        ("Discovered 50 tools (Raw prompt overhead: 28,646 tokens / turn)", (251, 191, 36)),
        ("", (0, 0, 0)),
        ("AUDIT FINDINGS ACROSS RULES TS001-TS010:", (239, 68, 68)),
        ("  • TS008 (Untyped property schemas)    : 83 errors", (239, 68, 68)),
        ("  • TS002 (Missing descriptions)        : 22 warnings", (251, 191, 36)),
        ("  • TS007 (Missing required array)      : 16 warnings", (251, 191, 36)),
        ("  • TS009 (Redundant empty wrappers)    : 16 warnings", (251, 191, 36)),
        ("  • TS004 (Excessive name length)       : 10 warnings", (203, 213, 225)),
        ("", (0, 0, 0)),
        ("✓ agentflight compile prunes schemas by up to 78% context savings!", (52, 211, 153)),
    ]
    cy = 152
    for l_text, col in lines:
        draw.text((40, cy), l_text, font=FONT_MONO, fill=col)
        cy += 24

    hud_x = 874
    draw.rounded_rectangle([(hud_x, 110), (1256, 620)], radius=8, fill=(16, 16, 32), outline=(99, 102, 241), width=1)
    draw.rounded_rectangle([(hud_x, 110), (1256, 140)], fill=(30, 24, 48))
    draw.text((hud_x + 16, 118), "TOOL ERGONOMICS HUD", font=FONT_MONO_BOLD, fill=(165, 180, 252))

    hud_items = [
        ("MCP ENDPOINT", "mcp.openany.si/mcp", (56, 189, 248)),
        ("TOOLS AUDITED", "50 Remote APIs", (203, 213, 225)),
        ("RAW OVERHEAD", "28,646 tokens/turn", (239, 68, 68)),
        ("COMPILED SAVINGS", "Up to 78% Context", (52, 211, 153)),
    ]
    hy = 160
    for lbl, val, col in hud_items:
        draw.text((hud_x + 16, hy), lbl, font=FONT_MONO_SM, fill=(148, 163, 184))
        draw.text((hud_x + 16, hy + 18), val, font=FONT_MONO_BOLD, fill=col)
        hy += 52

    draw_top_and_bottom_bars(draw, "06: Remote MCP Tool Ergonomics", "TS001-TS010 Static Linting & Token Pruning")
    draw_subtitle_bar(draw, "Audit OpenAny remote MCP tools against 10 ergonomics rules, trimming prompt schemas by up to 78% for maximum precision.")
    return img


def render_scene_7_frame(frame_idx: int, total_frames: int) -> Image.Image:
    """Scene 7: Outro with Ken Burns pull-back on 3D mission control background."""
    progress = frame_idx / max(1, total_frames)
    scale = 1.06 - 0.06 * progress
    w_crop = int(WIDTH / scale)
    h_crop = int(HEIGHT / scale)
    x1 = (WIDTH - w_crop) // 2
    y1 = (HEIGHT - h_crop) // 2
    cropped = HERO_IMG.crop((x1, y1, x1 + w_crop, y1 + h_crop))
    img = cropped.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 130))
    img.paste(overlay, (0, 0), overlay)
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([(140, 120), (1140, 560)], radius=16, fill=(10, 16, 32), outline=(16, 185, 129), width=2)
    draw.text((180, 150), "AgentFlight v1.2.0", font=FONT_BIG, fill=(255, 255, 255))
    draw.text((180, 205), "The Black-Box Flight Recorder & Cost Control Plane for AI Agents", font=FONT_SUB, fill=(52, 211, 153))

    draw.text((180, 255), "COMMERCIAL LAUNCH HIGHLIGHTS:", font=FONT_MONO_BOLD, fill=(251, 191, 36))
    draw.text((180, 285), "✔ Confirmed 30% Permanent Revenue Share on Attributed Usage\n✔ Outbound Header: X-OpenAny-Partner-Id: agentflight\n✔ Pre-Execution Cost Circuit Breakers (Zero-Credit Defense)\n✔ 0.08 μs Offline Replay & MCP Ergonomics Linter\n✔ 132/132 Tests Passed with Zero Regressions", font=FONT_MONO, fill=(203, 213, 225))

    draw.rounded_rectangle([(180, 420), (1100, 485)], radius=8, fill=(15, 23, 42), outline=(59, 130, 246), width=1)
    draw.text((200, 432), "INSTALL VIA PYPI:", font=FONT_MONO_SM, fill=(148, 163, 184))
    draw.text((200, 452), "$ pip install agentflight  &&  agentflight openany models", font=FONT_MONO_BOLD, fill=(56, 189, 248))

    draw.text((180, 510), "Owner: Akandwanaho Ivan Alvin  •  Live Portal: https://agentflight-tau.vercel.app", font=FONT_MONO_SM, fill=(148, 163, 184))

    draw_top_and_bottom_bars(draw, "Ready for Commercial Launch", "Available on PyPI and GitHub")
    draw_subtitle_bar(draw, "AgentFlight: The black-box telemetry and cost control plane for the agentic web. Available now on PyPI and GitHub.")
    return img


SCENE_RENDERERS = [
    render_scene_0_frame,
    render_scene_1_frame,
    render_scene_2_frame,
    render_scene_3_frame,
    render_scene_4_frame,
    render_scene_5_frame,
    render_scene_6_frame,
    render_scene_7_frame,
]


def main() -> int:
    out_dir = "marketing/openany-launch"
    os.makedirs(out_dir, exist_ok=True)
    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

    raw_video = os.path.join(out_dir, "raw_video_stream.mp4")
    final_makeover_mp4 = os.path.join(out_dir, "agentflight_openany_makeover_demo.mp4")
    final_master_mp4 = os.path.join(out_dir, "agentflight_openany_demo.mp4")
    final_gif = os.path.join(out_dir, "agentflight_openany_demo.gif")

    print("\n🎬 GENERATING AGENTFLIGHT × OPENANY MAKEOVER VIDEO")
    print(f"• Resolution: {WIDTH}x{HEIGHT} (720p HD @ {FPS}fps)")

    # 1. Build Audio Master
    print("\n[Step 1/3] Building synchronized voiceover narration & synth music track...")
    with tempfile.TemporaryDirectory() as tmp_audio_dir:
        audio_master_wav = build_master_audio(tmp_audio_dir, ffmpeg_bin)

        # 2. Render Video Frames
        print(f"\n[Step 2/3] Rendering video frames with Ken Burns zooms and animated HUDs...")
        total_frames = sum(int(dur * FPS) for _, _, dur in SCENE_SCRIPTS)
        writer = imageio_ffmpeg.write_frames(
            raw_video,
            (WIDTH, HEIGHT),
            fps=FPS,
            codec="libx264",
            pix_fmt_in="rgb24",
            output_params=["-preset", "fast", "-crf", "20"],
        )
        writer.send(None)

        curr_frame = 0
        sample_gif_frames = []
        t0 = time.perf_counter()

        for s_idx, (s_name, s_txt, s_dur) in enumerate(SCENE_SCRIPTS):
            scene_frame_count = int(s_dur * FPS)
            renderer = SCENE_RENDERERS[s_idx]
            for f in range(scene_frame_count):
                frame_img = renderer(f, scene_frame_count)
                writer.send(np.array(frame_img).tobytes())
                curr_frame += 1
                if f == scene_frame_count // 2:
                    sample_gif_frames.append(frame_img.resize((640, 360), Image.Resampling.LANCZOS))
            print(f"  • Rendered {s_name}: {scene_frame_count} frames ({curr_frame}/{total_frames})")

        writer.close()
        render_time = time.perf_counter() - t0
        print(f"  ✓ Video stream rendered in {render_time:.2f}s")

        # 3. Multiplex Video + Audio Master
        print(f"\n[Step 3/3] Multiplexing H.264 video + AAC stereo audio into final MP4...")
        subprocess.run([
            ffmpeg_bin, "-y",
            "-i", raw_video,
            "-i", audio_master_wav,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            final_makeover_mp4
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Update master demo file
        import shutil
        shutil.copy2(final_makeover_mp4, final_master_mp4)
        if os.path.exists(raw_video):
            os.remove(raw_video)

    # Export updated animated GIF preview
    if sample_gif_frames:
        sample_gif_frames[0].save(
            final_gif,
            save_all=True,
            append_images=sample_gif_frames[1:],
            duration=3500,
            loop=0,
        )

    file_size_mb = os.path.getsize(final_master_mp4) / (1024 * 1024)
    print("\n" + "=" * 70)
    print("  🚀 MAKEOVER DEMONSTRATION VIDEO COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print(f"• Final Video MP4 : {final_master_mp4} ({file_size_mb:.2f} MB)")
    print(f"• Makeover Video  : {final_makeover_mp4}")
    print(f"• Animated GIF    : {final_gif}")
    print(f"• Duration        : {total_frames / FPS:.1f} seconds")
    print("• Audio Track     : Voiceover Narration (Daniel en_GB) + Ambient Sci-Fi Synth + SFX")
    print("• Video Track     : 720p HD H.264 (Ken Burns 3D Hero Art + Animated HUDs + Subtitles)")
    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
