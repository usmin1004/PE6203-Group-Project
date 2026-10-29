# A1 — Foundations Build · starter notebooks

> **Reading this file.** This is a `.md` (Markdown) file — an ordinary plain-text file with a few
> light formatting marks in it. The `#`, `**` and `|` characters are formatting, not typos, and you
> need no special software to read it.
>
> **Easiest option: open `README.pdf` in this same folder instead.** Identical content, properly
> laid out. Otherwise: drag this file into a browser tab, or right-click it and choose *Open with →*
> **Notepad** (Windows) / **TextEdit** (Mac) / **VS Code**. Colab, GitHub and VS Code all display it
> with the formatting applied.

Three notebooks, one per part of A1. Each one already works end to end on a **placeholder domain**
(houseplants). Your job is to replace the placeholder with **your** domain — the same domain across
all three parts — and to do the thinking the brief asks for.

| File | Part | What it does |
|---|---|---|
| `PE6201_A1_Part1_Starter.ipynb` | Part 1 · Choose the right tool | Classifies the same test items twice — a trained scikit-learn classifier vs a foundation-model API call — and measures accuracy, cost, latency and effort side by side. |
| `PE6201_A1_Part2_Starter.ipynb` | Part 2 · Build a minimal retrieval system | Chunks and embeds your documents, retrieves the nearest passages, answers questions from them only, and gives you four tested ways to break it. |
| `PE6201_A1_Part3_Starter.ipynb` | Part 3 · Prompt and evaluate | A ten-case evaluation harness graded at two levels — L1 automatic assertions and an L2 judgement check — run across two prompt versions. |

A `.py` twin sits beside each `.ipynb`. They are the same file in two formats; open the `.ipynb`.

## How to run them

**Google Colab is the easy route.** Upload the `.ipynb`, then add your OpenRouter key as a Colab
secret named `OPENROUTER_API_KEY` (the key icon in the left sidebar) and give the notebook access.
The notebook picks it up automatically. Locally, set it as an environment variable of the same name.
If neither is present the notebook asks you to paste it, hidden.

**Never type your key into a code cell.** A key pasted into a cell gets saved into the notebook, and
the notebook goes into your submission ZIP.

Run every notebook **top to bottom** the first time, before changing anything. Seeing the placeholder
work is how you learn what a filled-in version looks like.

## What to change

Every line you need to touch is marked `### REPLACE ME`. Nothing else needs editing to submit —
though the cells marked `TRY THIS (knob)` are where the interesting findings come from, and the
brief rewards reporting what moved when you turned one.

**The placeholder domain is not a suggestion.** Do not submit houseplants. Pick a domain you
genuinely know — the brief explains why that matters and how to scope it.

## Cost

All three notebooks together make roughly 110 short calls. On the default model that is a small
fraction of one US cent, against a key sized to cover A1, A2 and the Project. Each notebook prints
its token count at the end, because cost is one of the things you are being asked to measure.

**Your allocation is fixed and will not be topped up.** Working to a budget — and choosing a model
you can afford — is part of what this course teaches, which is why Part 1 asks you to measure cost
in the first place. Keep the cheap default model unless your own numbers show it failing, set
`FAST_MODE = True` while you are debugging, and keep `temperature = 0` and `max_tokens` tight. The
FAQ has a fuller guide to choosing a model.

**Check what is left, often.** Every notebook has a `credit_check()` cell just after the setup —
run it at the start of a working session and again at the end. Checking is free; this endpoint is
not billed. From a terminal the same thing is:

```
curl https://openrouter.ai/api/v1/key \
  -H "Authorization: Bearer YOUR_OPENROUTER_API_KEY"
```

It returns `usage` (spent so far) and `limit` (your cap) in US dollars — what you have left is the
difference. The `rate_limit` field in the same reply is what you hit when a cell fails and then
works fine a minute later.

If a call fails with a rate-limit error, wait a minute and re-run that cell. If you are burning
credit unexpectedly fast, stop and email early — something specific is usually causing it, and it is
fixable while there is still time.

## Which parts need the API

| Part | Model calls | Runs locally and free |
|---|---|---|
| 1 | the API half of the comparison | the scikit-learn classifier |
| 2 | writing the answer | chunking, embedding, retrieval |
| 3 | the task, and the L2 judge if you use a model as judge | the L1 assertions |

Part 2 embeds locally because OpenRouter serves chat models, not embedding models — which is itself
the "which layer do you rent, and which do you own?" question from Class 2. If the local embedder
will not download, the notebook falls back to TF-IDF automatically and tells you it has done so.
That fallback matches **words** rather than **meaning**, which changes which failures you find — so
say in your writeup if you used it.

## Honesty, briefly

You may use an AI assistant on this assignment; the brief sets three conditions. Two of them bite
hardest here: **you must be able to explain every block of code you submit** — what it does and why
it is there, which is about function, not syntax — and **the numbers you report must be measurements
you actually ran**. An assistant will produce a plausible accuracy figure or a
convincing pass rate without running anything. The harnesses in these notebooks print real numbers —
use those.

## If something breaks

**These notebooks are a working draft, not gospel.** They were written before any of you ran them,
against library versions, model names and provider behaviour that change without notice. Assume they
will occasionally need repair.

When a cell fails, in this order:

1. **Read the error.** The last line of a Python traceback usually names the problem in plain words.
2. **Try to fix it yourself.** Debugging is part of the work, not a detour from it — and working out
   *why* something broke is Technical Execution and Reasoning at the same time.
3. **Report it** — in class or by email — with the cell, the **full** error text, and what you
   already tried. The shared copy gets fixed and the cohort gets told, so nobody behind you loses
   the same hour.

Reporting a problem costs you nothing and is not an admission that you are struggling. A starter
notebook is shared infrastructure; the first person to hit a bug and say so saves everyone after
them. **The one thing not to do is quietly work around a broken cell and say nothing** — if your fix
changes what the notebook measures (a different model, a smaller sample, a skipped check), say so in
your writeup. An unexplained deviation looks like a mistake; an explained one looks like judgement.

Common ones, already known:

- `ModuleNotFoundError` — re-run the `%pip install` cell at the top, then restart the runtime.
- The API returns nothing sensible — check `GEN_MODEL` is a model your key can reach
  (openrouter.ai/models), and that you have not run out of credit.
- A cell fails and then works a minute later — that is the rate limit, not a bug.
- Part 2 retrieves nothing useful — that is not a bug either. It is Part 2. Diagnose it.
- Anything else — check `PE6201_A1_FAQ.pdf` first; it defines accuracy, cost, latency, effort, scale,
  edge, system and harness with formulas, and answers the questions this assignment reliably
  produces. Then bring it to class or email. There is no such thing as a question too basic; if you
  are wondering, six other people are too.
