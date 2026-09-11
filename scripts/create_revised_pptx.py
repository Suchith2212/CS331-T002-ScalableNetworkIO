#!/usr/bin/env python3
import sys
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_slide_layout = prs.slide_layouts[6]

    # Color Palette
    COLOR_PRIMARY = RGBColor(15, 32, 67)    # Deep Navy Blue
    COLOR_ACCENT  = RGBColor(0, 114, 206)   # Cobalt Blue
    COLOR_TEXT    = RGBColor(40, 40, 40)    # Dark Charcoal
    COLOR_MUTED   = RGBColor(100, 100, 100) # Slate Gray
    COLOR_CARD_BG = RGBColor(245, 247, 250) # Light Gray/Blue

    def add_header(slide, title_text, category_text="CS331 COURSE PROJECT | TEAM T002"):
        # Category Banner
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
        tf = cat_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = category_text.upper()
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT

        # Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.7), Inches(0.8))
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.size = Pt(24)
        p.font.bold = True
        p.font.color.rgb = COLOR_PRIMARY

    # -------------------------------------------------------------
    # SLIDE 1: Problem Statement & Objectives
    # -------------------------------------------------------------
    slide1 = prs.slides.add_slide(blank_slide_layout)
    add_header(slide1, "Scalable Network I/O: From select to io_uring", "SLIDE 1 | PROBLEM STATEMENT & OBJECTIVES")

    # Team Info Box
    box_team = slide1.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.73), Inches(0.9))
    tf = box_team.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Team ID: T002  |  Project ID: 13  |  Members: Suchith (24110313), Rohith (24110303), Harshith (24110091), Hanook (24110378)"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY

    # Problem Card
    card_prob = slide1.shapes.add_textbox(Inches(0.8), Inches(2.6), Inches(5.6), Inches(4.3))
    tf = card_prob.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Problem Statement (The C10K Challenge)"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT

    bullets_prob = [
        "Traditional Network Servers: Spawn a dedicated OS thread per client connection.",
        "Memory Exhaustion: Thread stack allocations (~8MB default) quickly consume system RAM at scale.",
        "CPU Context Switching Thrashing: Managing thousands of threads causes intense context-switching overhead, destroying CPU cache locality.",
        "Resource Bottleneck: Systems collapse under context-switch overhead long before saturating physical network throughput."
    ]
    for b in bullets_prob:
        p = tf.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(14)
        p.font.color.rgb = COLOR_TEXT
        p.space_after = Pt(8)

    # Objectives Card
    card_obj = slide1.shapes.add_textbox(Inches(6.9), Inches(2.6), Inches(5.6), Inches(4.3))
    tf = card_obj.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Project Objectives"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT

    bullets_obj = [
        "Implementation: Build 5 standalone C TCP Echo Servers comparing Blocking, select(), poll(), epoll(), and io_uring.",
        "Paradigm Shift: Transition from O(N) synchronous readiness notification to O(1) kernel event queues and zero-syscall completion rings.",
        "Empirical Evaluation: Benchmark throughput (req/s), p99 latency, RAM RSS memory, and system call overhead from 10 to 5,000+ conns.",
        "Verification: Ensure 100% data integrity and clean TCP connection teardown."
    ]
    for b in bullets_obj:
        p = tf.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(14)
        p.font.color.rgb = COLOR_TEXT
        p.space_after = Pt(8)

    # -------------------------------------------------------------
    # SLIDE 2: Architecture / Mechanism
    # -------------------------------------------------------------
    slide2 = prs.slides.add_slide(blank_slide_layout)
    add_header(slide2, "Architecture & Engine Mechanics — Design & Implementation", "SLIDE 2 | ARCHITECTURE & MECHANISMS")

    box_arch = slide2.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.73), Inches(5.4))
    tf = box_arch.text_frame
    tf.word_wrap = True

    mechanisms = [
        ("1. Blocking Baseline (server_blocking.c)", "Thread-per-client model using pthread_create. Suffers from severe thread stack memory overhead (~12.4 MB RSS at 5k conns) and context switching latency."),
        ("2. select() Engine (server_select.c)", "Synchronous bitmask multiplexing (fd_set). Hard-capped at FD_SETSIZE (1024). Suffers from O(N) bitmask copying between user and kernel space."),
        ("3. poll() Engine (server_poll.c)", "Uses dynamic struct pollfd array. Removes 1024 cap, but still requires O(N) linear array scanning in kernel and user space."),
        ("4. epoll() Engine (server_epoll.c)", "O(1) Edge-Triggered (EPOLLET) event queue. Registers sockets once in an in-kernel Red-Black Tree. Interrupts populate an O(1) ready list."),
        ("5. io_uring Engine (server_uring.c)", "Lockless Submission Queue (SQ) and Completion Queue (CQ) ring buffers in shared memory. Enables zero-syscall batched asynchronous completion.")
    ]

    for title, desc in mechanisms:
        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(13)
        p2.font.color.rgb = COLOR_TEXT
        p2.space_after = Pt(10)

    # -------------------------------------------------------------
    # SLIDE 3: Extension / Issues Fixed / Evaluation
    # -------------------------------------------------------------
    slide3 = prs.slides.add_slide(blank_slide_layout)
    add_header(slide3, "Extensions Built, Bug Fixes & Empirical Evaluation", "SLIDE 3 | EXTENSION, ISSUES FIXED & RESULTS")

    # Fixes Left Column
    box_fixes = slide3.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(5.6), Inches(5.4))
    tf = box_fixes.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Extensions & Issues Fixed"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT

    fixes = [
        "Custom asyncio Load Harness: Re-architected benchmark harness from OS threads to Python asyncio to prevent host thread exhaustion at 5,000 conns.",
        "select() Buffer Protection: Added bounds checking (if client_fd >= FD_SETSIZE) to prevent memory corruption past 1024 sockets.",
        "EPOLLET Buffer Drain: Solved data starvation in Edge-Triggered epoll by looping non-blocking read/accept until EAGAIN/EWOULDBLOCK.",
        "io_uring CQE Batching: Implemented io_uring_peek_batch_cqe and explicit SQE re-arming for client accept lifecycle."
    ]
    for f in fixes:
        p = tf.add_paragraph()
        p.text = "• " + f
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT
        p.space_after = Pt(8)

    # Table Right Column
    box_table = slide3.shapes.add_textbox(Inches(6.7), Inches(1.5), Inches(5.8), Inches(5.4))
    tf = box_table.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Empirical Results Table"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT

    rows = [
        "Blocking  | 10k: 27.4k req/s | 5k: 32.3k req/s (12.4MB RSS)",
        "select()  | 10k: 89.6k req/s | >1024: EXCEEDED LIMIT",
        "poll()    | 10k: 78.5k req/s | 5k: 77.3k req/s (O(N) CPU)",
        "epoll()   | 10k: 75.6k req/s | 5k: 56.4k req/s (1.5MB RSS)",
        "io_uring  | 10k: 65.6k req/s | 5k: 46.3k req/s (0 Syscall)"
    ]
    for r in rows:
        p = tf.add_paragraph()
        p.text = "• " + r
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT
        p.space_after = Pt(10)

    # -------------------------------------------------------------
    # SLIDE 4: Non-Functional Testing Parameters
    # -------------------------------------------------------------
    slide4 = prs.slides.add_slide(blank_slide_layout)
    add_header(slide4, "Non-Functional Testing Parameters — Performance, Scalability & Reliability", "SLIDE 4 | NON-FUNCTIONAL TESTING")

    box_nft = slide4.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.73), Inches(5.4))
    tf = box_nft.text_frame
    tf.word_wrap = True

    nfts = [
        ("1. Performance (Throughput & p99 Latency)", "Evaluated throughput (req/s) and 99th percentile latency. select() and poll() achieve high throughput at medium load (~123k req/s), while epoll() maintains lowest latency variance under concurrency."),
        ("2. Scalability (Concurrency Capacity)", "Tested connection scaling from 10 to 5,000 active persistent connections. select() fails strictly past 1024 descriptors, whereas poll(), epoll(), and io_uring scale past 5,000 connections smoothly."),
        ("3. Reliability & Data Integrity", "Achieved 100% pass rate across all 5 servers on test_servers.py harness. Zero payload corruption, zero memory leaks, and clean TCP socket teardowns."),
        ("4. Memory Footprint Efficiency (RSS)", "Thread-per-client baseline consumed ~12.4 MB RSS at high load. epoll() maintained a sleek ~1.5 MB RSS footprint due to in-kernel Red-Black tree efficiency.")
    ]

    for title, desc in nfts:
        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(13)
        p2.font.color.rgb = COLOR_TEXT
        p2.space_after = Pt(10)

    # -------------------------------------------------------------
    # SLIDE 5: Challenges Faced & Key Lessons
    # -------------------------------------------------------------
    slide5 = prs.slides.add_slide(blank_slide_layout)
    add_header(slide5, "Challenges Faced & Key Engineering Lessons", "SLIDE 5 | CHALLENGES FACED")

    box_chal = slide5.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.73), Inches(5.4))
    tf = box_chal.text_frame
    tf.word_wrap = True

    chals = [
        ("1. System Descriptor Resource Limits (ulimit -n)", "Challenge: Default OS file descriptor limit (1024) blocked high-concurrency client connections.\nSolution: Tuned kernel limits via ulimit -n 65535 prior to running benchmark experiments."),
        ("2. Edge-Triggered Notification Misses in epoll()", "Challenge: EPOLLET mode stopped firing notifications when unread bytes remained in socket buffers.\nSolution: Re-architected read and accept routines into strict non-blocking loops draining until EAGAIN/EWOULDBLOCK."),
        ("3. Completion Ring Lifecycle in io_uring", "Challenge: Asynchronous SQE preparation and CQE tracking required careful user-data pointer mapping.\nSolution: Structured conn_info state contexts and batch harvesting via io_uring_peek_batch_cqe."),
        ("4. Harness Host Thread Exhaustion", "Challenge: Python multi-threading load generator crashed with 'can't start new thread' at 5,000 connections.\nSolution: Refactored harness to Python asyncio non-blocking socket loops.")
    ]

    for title, desc in chals:
        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(13)
        p2.font.color.rgb = COLOR_TEXT
        p2.space_after = Pt(10)

    output_path = "ppt/REVISED_5SLIDES.pptx"
    prs.save(output_path)
    print(f"Successfully generated PowerPoint deck at {output_path}!")

if __name__ == "__main__":
    build_presentation()
