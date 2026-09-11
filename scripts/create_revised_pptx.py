#!/usr/bin/env python3
import sys
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_slide_layout = prs.slide_layouts[6]

    # Color Palette
    COLOR_PRIMARY   = RGBColor(15, 23, 42)    # Dark Slate Navy
    COLOR_ACCENT    = RGBColor(2, 132, 199)   # Vibrant Azure Blue
    COLOR_TEXT_MAIN = RGBColor(30, 41, 59)    # Charcoal Body Text
    COLOR_MUTED     = RGBColor(100, 116, 139) # Slate Gray
    COLOR_CARD_BG   = RGBColor(248, 250, 252) # Soft Off-White
    COLOR_WHITE     = RGBColor(255, 255, 255) # Pure White
    COLOR_BORDER    = RGBColor(226, 232, 240) # Light Border Gray

    def add_header(slide, title_text, category_text):
        # Category Banner
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.35))
        tf = cat_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = category_text.upper()
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT

        # Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.7), Inches(0.7))
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
    add_header(slide1, "Scalable Network I/O: From select to io_uring", "CS331 COURSE PROJECT | TEAM T002 | PROJECT 13")

    # Team Banner Box
    team_card = slide1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(11.73), Inches(0.7))
    team_card.fill.solid()
    team_card.fill.fore_color.rgb = COLOR_PRIMARY
    team_card.line.color.rgb = COLOR_PRIMARY
    tf = team_card.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "TEAM ROSTER:  Suchith (24110313)  |  Rohith (24110303)  |  Harshith (24110091)  |  Hanook (24110378)"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE
    p.alignment = PP_ALIGN.CENTER

    # Left Card: Problem Statement
    card1 = slide1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(2.4), Inches(5.6), Inches(4.5))
    card1.fill.solid()
    card1.fill.fore_color.rgb = COLOR_CARD_BG
    card1.line.color.rgb = COLOR_BORDER
    tf1 = card1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "🛑 The C10K Concurrency Crisis"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY

    probs = [
        "Thread Overhead: Traditional servers spawn 1 OS thread per client -> 8MB stack allocation consumes system RAM.",
        "Context Thrashing: CPU spends more time switching thread contexts than processing network packets.",
        "Throughput Collapse: Systems crash long before saturating physical network bandwidth."
    ]
    for pb in probs:
        p = tf1.add_paragraph()
        p.text = "• " + pb
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(12)

    # Right Card: Objectives
    card2 = slide1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.9), Inches(2.4), Inches(5.6), Inches(4.5))
    card2.fill.solid()
    card2.fill.fore_color.rgb = COLOR_CARD_BG
    card2.line.color.rgb = COLOR_BORDER
    tf2 = card2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "🎯 Core Project Objectives"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT

    objs = [
        "Build 5 C Servers: Implement Blocking, select(), poll(), epoll(), and io_uring engines from scratch.",
        "Paradigm Shift: Transition from O(N) synchronous polling to O(1) event queues and zero-syscall completion rings.",
        "Empirical Evaluation: Profile throughput, p99 latency, RAM RSS, and syscall overhead from 10 to 5,000+ connections."
    ]
    for ob in objs:
        p = tf2.add_paragraph()
        p.text = "• " + ob
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(12)

    # -------------------------------------------------------------
    # SLIDE 2: Architecture & Mechanism
    # -------------------------------------------------------------
    slide2 = prs.slides.add_slide(blank_slide_layout)
    add_header(slide2, "Evolution of Linux Socket I/O Multiplexing", "SLIDE 2 | ARCHITECTURE & MECHANISMS")

    card_arch = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(11.73), Inches(5.4))
    card_arch.fill.solid()
    card_arch.fill.fore_color.rgb = COLOR_CARD_BG
    card_arch.line.color.rgb = COLOR_BORDER
    tf_arch = card_arch.text_frame
    tf_arch.word_wrap = True

    mechanisms = [
        ("1. Blocking Baseline (server_blocking.c)", "Thread-per-client model using pthread_create -> High thread stack allocation (~12.4 MB RSS at 5k conns) & CPU context-switching cost."),
        ("2. select() Engine (server_select.c)", "Synchronous fd_set bitmask multiplexing -> Bitmasks copied to/from kernel every iteration -> HARD CAP: FD_SETSIZE (1024 FDs)."),
        ("3. poll() Engine (server_poll.c)", "Dynamic struct pollfd array -> Removes 1024 cap, but suffers O(N) linear array scanning penalty in kernel and user space."),
        ("4. epoll() Engine (server_epoll.c)", "O(1) Edge-Triggered (EPOLLET) event queue -> In-kernel Red-Black Tree stores sockets once; interrupts populate an O(1) ready list (~1.5 MB RSS)."),
        ("5. io_uring Engine (server_uring.c)", "Shared lockless Submission (SQ) & Completion (CQ) ring buffers -> Enables ZERO per-I/O system call context switches.")
    ]

    for idx, (title, desc) in enumerate(mechanisms):
        p = tf_arch.paragraphs[0] if idx == 0 else tf_arch.add_paragraph()
        p.text = title
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT

        p2 = tf_arch.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(13)
        p2.font.color.rgb = COLOR_TEXT_MAIN
        p2.space_after = Pt(10)

    # -------------------------------------------------------------
    # SLIDE 3: Extension / Issues Fixed / Evaluation
    # -------------------------------------------------------------
    slide3 = prs.slides.add_slide(blank_slide_layout)
    add_header(slide3, "Engineering Extensions, Fixes & Empirical Evaluation", "SLIDE 3 | EXTENSION, ISSUES FIXED & RESULTS")

    # Fixes Left Column
    card_fix = slide3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(5.6), Inches(5.4))
    card_fix.fill.solid()
    card_fix.fill.fore_color.rgb = COLOR_CARD_BG
    card_fix.line.color.rgb = COLOR_BORDER
    tff = card_fix.text_frame
    tff.word_wrap = True
    p = tff.paragraphs[0]
    p.text = "🛠️ Key Engineering Fixes Delivered"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT

    fixes = [
        "asyncio Benchmark Harness: Rebuilt load harness from OS threads to Python asyncio loops, preventing host thread crashes at 5,000 connections.",
        "select() Protection Guard: Added descriptor bounds check (if client_fd >= FD_SETSIZE) to prevent bitmask memory corruption past 1024 sockets.",
        "EPOLLET Buffer Drain: Solved data starvation in Edge-Triggered epoll by looping non-blocking read/accept until EAGAIN/EWOULDBLOCK."
    ]
    for f in fixes:
        p = tff.add_paragraph()
        p.text = "• " + f
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(12)

    # Table Right Column
    card_tb = slide3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.9), Inches(1.5), Inches(5.6), Inches(5.4))
    card_tb.fill.solid()
    card_tb.fill.fore_color.rgb = COLOR_CARD_BG
    card_tb.line.color.rgb = COLOR_BORDER
    tft = card_tb.text_frame
    tft.word_wrap = True
    p = tft.paragraphs[0]
    p.text = "📊 Benchmark Evaluation Summary"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY

    rows = [
        "Blocking  | 32.3k req/s @ 5k conns | High RAM RSS (~12.4 MB)",
        "select()  | 87.4k req/s @ 1k conns | Exceeded Limit past 1024 FDs",
        "poll()    | 77.3k req/s @ 5k conns | O(N) CPU array scanning penalty",
        "epoll()   | 56.4k req/s @ 5k conns | O(1) Event queue (~1.5 MB RSS)",
        "io_uring  | 46.3k req/s @ 5k conns | Zero per-I/O system call cost"
    ]
    for r in rows:
        p = tft.add_paragraph()
        p.text = "• " + r
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(14)

    # -------------------------------------------------------------
    # SLIDE 4: Non-Functional Testing Parameters
    # -------------------------------------------------------------
    slide4 = prs.slides.add_slide(blank_slide_layout)
    add_header(slide4, "Non-Functional Testing: Performance, Scalability & RAM", "SLIDE 4 | NON-FUNCTIONAL TESTING")

    card_nft = slide4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(11.73), Inches(5.4))
    card_nft.fill.solid()
    card_nft.fill.fore_color.rgb = COLOR_CARD_BG
    card_nft.line.color.rgb = COLOR_BORDER
    tfn = card_nft.text_frame
    tfn.word_wrap = True

    nfts = [
        ("⚡ Performance (Throughput & Latency)", "Peak throughput achieved by poll() and select() at medium load (~123k req/s). Lowest latency variance maintained by epoll() Edge-Triggered mode."),
        ("📈 Scalability (10 to 5,000+ Sockets)", "select() fails strictly past 1024 file descriptors. poll(), epoll(), and io_uring scale past 5,000 connections seamlessly."),
        ("🔒 Reliability & Data Integrity", "Achieved 100% pass rate across 5/5 servers on automated correctness suite (test_servers.py) with zero payload corruption and clean TCP socket teardowns."),
        ("💾 Memory Footprint Efficiency (RSS)", "Thread-per-client baseline consumed ~12.4 MB RSS at high load. epoll() maintained a sleek ~1.5 MB RSS footprint due to in-kernel Red-Black tree efficiency.")
    ]

    for idx, (title, desc) in enumerate(nfts):
        p = tfn.paragraphs[0] if idx == 0 else tfn.add_paragraph()
        p.text = title
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT

        p2 = tfn.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(13)
        p2.font.color.rgb = COLOR_TEXT_MAIN
        p2.space_after = Pt(10)

    # -------------------------------------------------------------
    # SLIDE 5: Challenges Faced & Lessons Learned
    # -------------------------------------------------------------
    slide5 = prs.slides.add_slide(blank_slide_layout)
    add_header(slide5, "Engineering Challenges Faced & Technical Solutions", "SLIDE 5 | CHALLENGES FACED")

    card_ch = slide5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(11.73), Inches(5.4))
    card_ch.fill.solid()
    card_ch.fill.fore_color.rgb = COLOR_CARD_BG
    card_ch.line.color.rgb = COLOR_BORDER
    tfc = card_ch.text_frame
    tfc.word_wrap = True

    chals = [
        ("⚠️ Challenge 1: System File Descriptor Resource Limits (ulimit -n)", "Fix: Tuned OS kernel limits to ulimit -n 65535 to prevent client load generator connection rejections."),
        ("⚠️ Challenge 2: Edge-Triggered Notification Misses in epoll()", "Fix: Re-architected read/accept routines into non-blocking loops draining until EAGAIN/EWOULDBLOCK."),
        ("⚠️ Challenge 3: Completion Ring State Mapping in io_uring", "Fix: Structured conn_info state pointer contexts and implemented batch harvesting via io_uring_peek_batch_cqe."),
        ("⚠️ Challenge 4: Harness Host Thread Exhaustion", "Fix: Refactored multi-threaded load generator to non-blocking Python asyncio event loops.")
    ]

    for idx, (title, desc) in enumerate(chals):
        p = tfc.paragraphs[0] if idx == 0 else tfc.add_paragraph()
        p.text = title
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT

        p2 = tfc.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(13)
        p2.font.color.rgb = COLOR_TEXT_MAIN
        p2.space_after = Pt(10)

    output_path = "ppt/REVISED_5SLIDES_V2.pptx"
    prs.save(output_path)
    print(f"Successfully generated clean PowerPoint deck at {output_path}!")

if __name__ == "__main__":
    build_presentation()
