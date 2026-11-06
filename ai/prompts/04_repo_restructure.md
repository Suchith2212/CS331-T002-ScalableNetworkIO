# Prompt 04: Repository Restructure

```markdown
CONTEXT
This repo is my Computer Networks project (I/O multiplexing benchmark: blocking, select, poll,
epoll, io_uring echo servers in C). I must restructure it to EXACTLY this top-level layout:

  README.md
  /code     -> all source code
  /report   -> final report (PDF)
  /ppt      -> presentation slides (PDF or .pptx)
  /ai       -> all AI prompts and conversations (new ones; delete the old ones)

Current state (from my file explorer): root has .vscode/, AI_Used/ (Prompts.md, Step_By_Step.md,
Thought_Process.md, Tools.md), code/ (bin, include, loadgen, results, scripts, src, Makefile),
PPTX/ (Final_Presentation.pptx), report/ (final_report.md, FINAL_REPORT.pdf), a root-level
results/ folder, .gitignore, CHANGES.md, FINDINGS.md, README.md (and maybe FINDINGS_v2.md).

SAFETY RULES
 - Before touching anything: run `git status`, make sure the tree is clean or commit a
   snapshot commit "snapshot before restructure", and create a branch `restructure`.
 - Use `git mv` for every move so history is preserved. Windows is case-insensitive, so for
   case-only renames use a two-step move (PPTX -> ppt_tmp -> ppt).
 - Never delete anything that is not on the explicit delete list below. If a file's purpose is
   unclear, leave it and list it in your final report.
 - Do not push. Commit locally and stop for my review.

TASK 1: move into the required layout
 a) PPTX/ -> ppt/ (keep Final_Presentation.pptx; if a PDF export is easy to produce, add it, otherwise skip).
 b) report/: keep FINAL_REPORT.pdf as the deliverable. If final_report.md is newer than the PDF,
    tell me the PDF is stale. Do not regenerate it unless I ask. Keep final_report.md in
    report/ as the source.
 c) Root CHANGES.md, FINDINGS.md, FINDINGS_v2.md -> code/docs/ (create it).
 d) Root-level results/ -> merge into code/results/. Compare file names and contents first;
    never overwrite a differing file. If names clash, keep both (suffix _root) and list them.
 e) .vscode/ stays out of git: add it to .gitignore if it isn't already. Do not delete it locally.
 f) code/bin/ (compiled binaries) must be git-ignored and untracked (`git rm -r --cached code/bin`
    if tracked). Add *.o, binaries and __pycache__ to .gitignore too.

TASK 2: /ai folder (replace the old one)
 - Delete the old AI_Used/ folder ONLY AFTER ai/ exists and contains the new files below
   (use `git rm -r AI_Used`).
 - Create ai/ with this structure:
     ai/README.md           explains what is in the folder and which tool/model produced what
     ai/prompts/            one file per prompt, numbered, e.g. 01_epoll_io_uring_fixes.md,
                            02_followup_experiments.md, 03_new_client_loadgen.md,
                            04_repo_restructure.md
     ai/conversations/      full chat transcripts, one file per session
 - I will paste the real prompts and conversation exports myself. Create the files with a
   header and the text "PASTE HERE" as placeholders. Do NOT invent or reconstruct prompt text
   or conversations. For 04_repo_restructure.md, you may paste this very prompt.
 - In your final report, list which placeholder files I still need to fill.

TASK 3: fix everything the move can break
 - Check the Makefile, scripts in code/scripts/, and the #include paths ("../include/common.h")
   still resolve. Update only relative paths that broke because of the move.
 - Search the repo (including README, report/*.md, ppt notes if readable) for references to
   old paths: AI_Used, PPTX/, root results/, CHANGES.md, FINDINGS.md. Update them.
 - Look at code/src/: server_epoll.c, server_uring.c and the *_v1.c baseline files. Check
   whether the Makefile or scripts reference them. Do NOT delete them. Tell me which are
   unreferenced, and propose either keeping them in code/src/baseline/ or removing them.
 - Run `make clean && make` (with -Wall -Wextra) and confirm every server builds.
 - Run the quick echo test ("hello" -> "hello") against each server, if the script exists.

TASK 4: README.md (root)
 Rewrite it to contain, without inventing facts:
  - one-paragraph project description
  - the folder structure (the 5 items above, plus the contents of code/: src, include,
    loadgen, scripts, results, docs, Makefile)
  - how to build (`cd code && make`), how to run each server, and how to run the benchmark
    scripts, using the real script names from code/scripts/
  - requirements: Linux kernel version, liburing version, compiler (read them with `uname -r`
    and `pkg-config --modversion liburing`)
  - a pointer to report/FINAL_REPORT.pdf and ppt/Final_Presentation.pptx
  - a short note that all AI usage is documented in /ai
 Keep any real content from the existing README that is still accurate.

DELIVERABLES
 1. The restructured tree committed on branch `restructure` in logical commits
    (moves / ai folder / path fixes / README).
 2. Output of `git status` and `tree -L 3 -I 'bin|.git'` (or equivalent) at the end.
 3. A list of: files you moved, files you deleted, files you left alone and why, broken
    references you fixed, placeholders I must fill, and anything that needs my decision.
 4. Confirm that the top level contains only: README.md, code/, report/, ppt/, ai/ plus
    dotfiles (.git, .gitignore, .vscode).
```
