# Tasks: Diary Adapter

**Input**: Design documents from `/specs/008-diary-adapter/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R14), data-model.md, quickstart.md

**Tests**: REQUIRED — Constitution VIII (code without its tests in the same change is
incomplete) and FR-007 (the documented rules gated hermetically). Prose and test tasks are
paired inside each story; a story's checkpoint is `make verify` green, and the phase — not
the individual task — is the commit seam.

**Organization**: By user story, in the spec's own order. After Phase 2, US1 (format
resolution), US2 (the write and its link) and US3 (ordering consumption) touch disjoint files
and none blocks another. The P1 MVP seam is US1 + US2; US3 is P2.

**Artifact converge round 1 applied** (2 lenses, 25 findings — 23 fixed, 1 defended, 1
accepted-as-recorded). The fixes that changed this file's shape: the entry **title** is split
out of the compared structure (otherwise every fixture classifies inconsistent and the
"consistent" fixture's expected notice set is unsatisfiable); date-token padding and
cross-entry ambiguity resolution are pinned as explicit, implementable rules; `skills/diary/`
trips slice 7's `SCANNED_SKILL_DIRS` guard, so the naming scan and its registration move into
Phase 1; the op-fidelity gate needs a mask or it fails the prose FR-001 mandates; the
`MINIMAL_DEFAULT` import-time derivation was a Phase-2/Phase-3 circular dependency and is
replaced by two named constants with an agreement gate; and `test_diary.py` (slice 1) already
gates the raw contract behavior three of these modules were about to re-assert. The **defended**
finding: both lenses flagged that `commands/close.md` treats the derived timeline as a draft
input while spec FR-005 says it is not — see T013, which narrows this slice's claim to one
that is true under either ordering rather than amending a landed sibling.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1–US3 per spec.md

---

## Phase 1: Setup

**Purpose**: the two files whose *existence* no story may own (so a scope cut can never
orphan a later task), the repo guard that firing is the point of, and the shared fixtures.

- [x] T001 Create the diary skill's surface **and its naming scan together** — they cannot be
      separated, because slice 7's `test_every_skill_directory_is_covered_by_a_naming_scan`
      (`tests/contract/test_catalog_prose.py`) asserts every directory under `skills/` appears
      in `SCANNED_SKILL_DIRS`, and creating `skills/diary/` without a scan turns `make verify`
      red by design ("a skill added without one is silently exempt"):
      (a) `skills/diary/SKILL.md` — frontmatter with `name: diary` and a when-to-use
      `description`, a one-paragraph overview, and empty section stubs for *interface /
      write flow / drafting handoff / non-goals*. US2 (T012–T014) fills the first three; T019
      completes the non-goals. `skills/diary/references/` is **not** created here and needs no
      `.gitkeep` — git carries no empty directory, so it materializes when T008 writes
      `references/format.md`.
      (b) `tests/contract/test_diary_prose.py` — the module, carrying doc-set discovery
      (`rglob("*.md")` over `skills/diary/`), a non-vanishing guard whose **target** set is
      `{SKILL.md, references/format.md}` but which ships asserting only `SKILL.md` until T008
      widens it (mark that inline with the task that does), **and the SC-006 naming scan
      itself**: import the **merged** `DENY_PATTERNS` from
      `tests/contract/test_command_capability_naming.py` and `FENCE_RE` from
      `tests/contract/test_skill_capability_naming.py` — both shared mechanisms, never
      slice-local copies, following `tests/contract/test_investigation_prose.py`'s precedent of
      importing exactly those two. The merged set is the right one **specifically for this
      skill**: it is the one that carries the document-store vendors (`confluence`, `notion`,
      `sharepoint`, `dropbox`), and a doc whose subject *is* a document is the doc most likely
      to name one. Run it over every discovered doc, and add the `mcp__` literal hard fail on
      **raw** text, fenced or not.
      Record inline, as a note to T013: the merged set bans `confluence` and `notion`, which
      FR-004 *requires* the skill to name as deferred adapters — so **T013 lands that sentence
      and its mask together**. Do not build the mask here; a mask with nothing to mask is the
      vacuous gate this repo's own precedent warns about.
      (c) Add `"diary"` to `SCANNED_SKILL_DIRS` in `tests/contract/test_catalog_prose.py`.
      Because (b) lands in the same task, that listing is **truthful, not a rubber stamp** —
      the same standard the existing comment there sets for `investigation`.
- [x] T002 Create the shared fixture entry sets under `tests/fixtures/diary/`, exactly per
      data-model.md §10's roster. Each file is a JSON object
      `{"description": str, "entries": [Entry]}` where every `Entry` is
      `{"link", "content", "at"}` and the list is **newest-first** — the shape
      `read_recent(n)` returns, so a fixture is consumed exactly as the contract delivers it
      and no test ever has to reorder one. `at` values are ISO-8601 and strictly decreasing
      down the list; they exist to make the newest-first claim checkable and are **never**
      read by extraction (FR-002). Eight files:
      **`entries-consistent.json`** — 5 entries. Each has its own H1 title line
      (`# 2026-07-21 — checkout: elevated latency`, dates and titles differing per entry —
      that is what real diaries look like, and data-model §3 excludes the title from the
      compared triple precisely so this set is still *consistent*), followed by the **same
      four `##` section headings in the same order** in every entry. ISO dates throughout.
      **`entries-bold.json`** — 5 entries whose section labels are whole-line `**What
      happened**` form with no `#` anywhere; give them a bold title line too, so the `title`
      split is exercised for the `bold` marker as well as `atx`.
      **`entries-inconsistent.json`** — 5 entries where entries 2–5 share one section order
      and the **newest** entry uses a different one. The difference must be in the compared
      triple (section headings / `field_order` / `date_format`), not merely in body prose, or
      the freshest-wins assertion is vacuous.
      **`entries-ambiguous-date.json`** — 5 entries, every date `03/04/2026`-shaped with
      **both** components ≤ 12 in **every** entry, so the pass cannot resolve the order.
      **`entries-disambiguating.json`** — same style, except the **third-newest** entry is
      dated with a component > 12. Pin the position: it decides both the freshest-wins result
      and the expected notice set, which T010 compares exactly. Its section headings match the
      rest of the set, so the only cross-entry difference is the one the ambiguity pass
      resolves. **Put the > 12 component FIRST** (e.g. `17/06/2026`, not `03/17/2026`): the
      provisional labelling of data-model §3.1 step 1 is already first→`MM`, second→`DD`, so a
      disambiguator in the *second* slot adopts an order byte-identical to the provisional one
      — and then an implementation that never inspects the unambiguous entry at all, and merely
      clears every flag, produces the same result as a correct one. The whole fixture exists to
      make order **adoption** observable, so the adopted order must differ from the provisional
      one.
      **Both date fixtures**: choose a sequence that is strictly decreasing under *both*
      readings while keeping every component ≤ 12 in the ambiguous set — e.g. `09/08`, `08/07`,
      `07/06`, `06/05`, `05/04` — so the narrative dates agree with `at` under either
      interpretation. A set whose titles contradict `at` in every reading is not diary data any
      reviewer can cross-check.
      **No fixture's body text may begin a line with a `digit:` token** (e.g. a bare `14:12`
      opening a timeline line). `field_order` draws from line-initial `Label:` inline fields,
      and a clock time is the one thing that looks like a label but varies per entry — it would
      make the *baseline* fixture classify as inconsistent. Write `At 14:12 the alert fired.`
      instead. (data-model §3 pins the pattern letter-anchored as the other half of this.)
      **`entries-short.json`** — exactly 2 entries, otherwise shaped like `entries-consistent`.
      **`entries-empty.json`** — `"entries": []`.
      **`entries-labeled-causal.json`** — 1+ entries whose sections carry the close flow's
      causal proposal labels verbatim, **plus a top-level `"sections"` key**: the ordered
      `[label, block]` pairs `apply_format` consumes (data-model §8). Without it T010's
      pass-through assertion has no input. Include at least one block whose label carries
      punctuation and one whose text ends in a trailing space, so byte-preservation is a real
      assertion rather than a trivially-satisfied one, plus one block whose label appears in
      **no** heading, to exercise the no-content-dropped rule.
- [x] T003 [P] Write `tests/fixtures/diary/README.md`: the fixture format decision (plain
      JSON, stdlib `json`, newest-first, `at` strictly decreasing and never read by
      extraction), one line per fixture naming **what it discriminates** (i.e. which assertion
      would still pass if that fixture were replaced by `entries-consistent.json` — if the
      answer is "all of them", the fixture is not pulling its weight), and how a mock-seeded
      test converts a fixture to diary state: iterate `reversed(entries)` calling
      `diary.append_entry(entry["content"])`, letting the mock mint its own `link`/`at`, so the
      fixture stays the single source and no test hand-writes seed data. State the consequence
      explicitly, because it is the trap: mock-returned entries therefore never `==` the
      fixture's entries, so an ordering assertion must compare
      `[e["content"] for e in returned]` against the fixture's content order.

**Checkpoint**: `make verify` green — including slice 7's skill-coverage guard, which T001(c)
is what keeps green.

---

## Phase 2: Foundational

**Purpose**: the reference-encoding module and the constants every story asserts against.
**Blocking** — US1 and US3 both import this module.

- [x] T004 Create `tests/helpers/diary_reference.py` with the module docstring that states, in
      the house style of `tests/helpers/catalog_reference.py`, what this module **is** (the
      dev-only CI instrument that lets `skills/diary/`'s documented rules be exercised by
      hermetic tests instead of asserted on prose — Constitution VIII) and what it **is NOT**
      (proof that a live agent follows that prose when it drafts a real entry — design §10's
      scenario-harness territory). Stdlib only (`json`, `re`, `inspect`, `pathlib`); plain
      functions over plain dicts, no classes, no dataclasses; each step's comment citing the
      prose section it encodes. Nothing here ships (Constitution I; FR-008).
- [x] T005 Add the module-level constants to `tests/helpers/diary_reference.py`, exported so
      the prose gates (T023) can assert them **both ways** — a doc naming a notice the encoding
      never emits is as wrong as one losing a notice:
      `NOTICE_KINDS = frozenset({"template_malformed", "entries_inconsistent",
      "date_ambiguous", "template_candidate"})`;
      `FORMAT_INPUT_KEYS = frozenset({"template", "entries", "content"})`;
      `STRUCTURE_PARTS = ("title", "sections", "date_format", "field_order")`;
      `DEFAULT_READ_DEPTH = 5`, commented with research R2, the config key
      `battleBuddy.diary.recentEntries`, **and R14's recorded fact that no landed consumer
      reads that key yet**;
      `MINIMAL_DEFAULT_TEXT` (the data-model §6 skeleton verbatim) and `MINIMAL_DEFAULT` (its
      `Structure`), as **two hand-written constants**. They are not derived from each other:
      the skeleton's title line contains the literal tokens `YYYY-MM-DD` rather than a date, so
      extraction finds no date-bearing line there — deriving at import would both contradict
      a Phase-2→Phase-3 circular dependency. That is the **only** reason: thanks to
      data-model §3's pattern-language rule, `extract_structure(MINIMAL_DEFAULT_TEXT)` does
      reproduce `MINIMAL_DEFAULT` exactly, `date_format` included — so T023 gates their
      agreement **in full**, not partially. Comment that at the constant.

**Checkpoint**: `make verify` green — the module imports cleanly and asserts nothing yet.

---

## Phase 3: User Story 1 — the close-time entry reads like the team wrote it (P1)

**Goal**: format resolution and structure extraction, documented and gated.

**Independent test**: run the decision rules and extraction over the fixture entry sets —
template-configured selects the template; template-absent matches observed structure; goldens
match field-for-field, including the empty-diary default and freshest-wins.

- [x] T006 [US1] Implement extraction in `tests/helpers/diary_reference.py`:
      `extract_structure(content) -> Structure` per data-model.md §3, returning
      `{title, sections, date_format, field_order}`.
      Heading recognition is exactly two shapes — `atx` (`#{1,6} <text>`, `level` = the `#`
      count) and `bold` (the **whole** line is `**<text>**`, `level` = `None`). A line that is
      merely *partly* bold is not a heading; the anchored regex is the rule, and the comment
      says so, since "contains bold" is the misreading a later author would reach for.
      `title` is the **first** heading when it is the date-bearing line, and is excluded from
      both `sections` and `field_order` — with the comment explaining why (a per-entry title
      would otherwise make every real diary compare as inconsistent; research R4(a)).
      `date_format` is derived from the first date-bearing line by replacing recognized
      components with `YYYY|YY|MM|M|DD|D|Mon|Month` and keeping every other character literal,
      under the **pinned padding rule**: a numeric component written with two digits takes the
      padded token, one digit takes the unpadded one — padding is a property of how the
      component is *written*, not of its value (so `21 Jul 2026` → `DD Mon YYYY`). **`at` is
      never consulted** (FR-002) — assert-worthy enough that the function does not take it as
      a parameter at all.
      For a numeric date whose components are both ≤ 12, set `ambiguous: true` and label them
      provisionally in the order they appear (first → `MM`, second → `DD`); the flag is what
      makes the labelling provisional rather than a silent pick.
      `field_order` is the ordered, first-occurrence-wins list of normalized labels (lowercase,
      trailing `:` stripped, internal whitespace collapsed) drawn from `sections` heading texts
      plus line-initial `Label:` inline fields. An entry with no headings and no inline fields
      yields empty lists and whatever `date_format` was found — a legal empty-shaped structure,
      never an exception.
- [x] T007 [US1] Add `resolve_date_ambiguity(structures) -> structures` to
      `tests/helpers/diary_reference.py` (data-model §3.1): scan every structure from one read;
      if **any** carries an unambiguous numeric date, adopt its component order for all of them
      and clear every `ambiguous` flag; if none does, leave the flags standing. It runs
      **before** the consistency comparison — comment why: a resolved and an unresolved entry
      would otherwise disagree on `pattern` and trip a spurious `entries_inconsistent`. It is a
      separate named function because a single-entry `extract_structure` cannot answer a
      cross-entry question, and hiding the step inside `resolve_format` would leave the
      per-entry goldens undefined.
- [x] T008 [US1] Write `skills/diary/references/format.md` — the normative rules T006/T007/T009
      encode, and the doc Phase 6's gates read. It must state, in prose an agent can follow:
      the resolution decision in order (configured template wins outright, **and no
      recent-entry read is needed for formatting** when it does; malformed template falls back
      to match-recent with the problem surfaced; entries present → match them; no entries →
      the minimal default, offered as a template candidate); the read depth (5 by default,
      `battleBuddy.diary.recentEntries` to change it); **absent versus malformed** — the key
      absent or its value null is *absent*; a configured value that is not a string, or is
      empty or whitespace-only, is *malformed* — and that a template with no headings is a
      legitimate flat style, not a defect; the extraction rules (both heading shapes; why the
      entry title is not part of the compared shape; the date-format tokens with worked
      examples **and the padding rule**; field-order normalization); the four `STRUCTURE_PARTS`
      by name; that `content` is the extraction surface and `at` is machine ordering metadata
      that is never the team's date format; that extraction is **bounded** — it reads an entry
      for its title, headings, date rendering and field order and yields only those, so a very
      long entry costs the matching step nothing extra and no entry *body* is ever carried into
      the draft or into any store (spec edge case "very long recent entries"); consistency
      detection across the entries read and **freshest-wins** on any difference, with the drift
      surfaced; numeric date ambiguity — the pass-level scan, and if it resolves nothing,
      **surface it for the responder to confirm rather than picking silently**; the minimal
      default skeleton verbatim, including that its `Evidence` section carries the in-session
      evidence links **as gathered** (`{url, excerpt}` pairs, Constitution IV) and never a
      prose summary; the four notice kinds by name; the ordering-consumption rule — entries
      arrive most recent first and are **used as-is: consumers never re-sort**, *and* the
      adapter-side half of the same commitment, that **an adapter over an oldest-first store
      reverses on read** so its consumers never have to (T020's mask exists for exactly this
      sentence and is vacuous without it); and that row fields are not inputs to any of this.
      Then widen T001's non-vanishing guard in `tests/contract/test_diary_prose.py` to the full
      target set `{SKILL.md, references/format.md}` and delete the inline note pointing here.
- [x] T009 [US1] Implement the decision and the transform in
      `tests/helpers/diary_reference.py`:
      `resolve_format(template, entries) -> FormatResolution` per data-model.md §4 — `None`
      template means absent; a non-string or blank template is malformed, emits
      `template_malformed`, and falls through; entries present produce `source="matched"` after
      running T007's ambiguity pass and then §5's comparison on the triple
      (**sections'** heading texts in order, `date_format.pattern`, `field_order`) — all equal →
      that structure; any difference → the newest entry's structure plus `entries_inconsistent`;
      an unresolved ambiguity emits `date_ambiguous`; no entries produce `source="default"` with
      `MINIMAL_DEFAULT` plus `template_candidate`. When `source="template"` the function must
      **not** touch `entries` at all — that is US1 AS-1's "no recent-entry read is needed", and
      the way to make it observable rather than claimed is for the template branch to return
      before any entry is read (T011 asserts it with a value that would raise if read).
      `apply_format(structure, sections) -> content` per data-model.md §8 — mechanical
      arrangement only: `sections` is an ordered list of `[label, block]` pairs; blocks are
      **opaque strings in, byte-identical strings out**; headings are re-emitted in the resolved
      structure's markers and levels; sections are ordered by `field_order` matched on
      normalized label; a label with no matching section is omitted; a section with no matching
      label is appended after the structured ones at the modal level of `structure.sections`
      (level 2 when empty), so **no content is ever dropped**.
      Date rendering lives in a separate `render_date(date_format, date)` and is deliberately
      **not** part of the resolution path or of `apply_format`.
- [x] T010 [US1] Write the two expectation fixtures:
      `tests/fixtures/diary/golden-structures.json` — fixture-set name → **a list of expected
      `Structure`, one per entry, in fixture order** (extraction is per-entry, so a single
      structure per set is not well-defined for the inconsistent and disambiguating sets), each
      compared field-for-field (SC-003), plus a `MINIMAL_DEFAULT` entry; and
      `tests/fixtures/diary/resolution-matrix.json` — one case per (template state × entry set)
      carrying `expected_source`, the exact expected **notice set**, and the expected
      **resolved** structure (the pass-level answer, after ambiguity resolution and the
      consistency comparison). Template states covered: absent (`null`), well-formed string,
      non-string as a JSON number, non-string as a JSON object (two rows — "not a string" has
      more than one shape), empty string, whitespace-only. Notices are compared as **sets and
      exactly**, never "contains", so a spurious extra notice fails.
- [x] T011 [US1] Write `tests/contract/test_diary_format.py`, parametrized off the two
      expectation fixtures (no hand-written expectations in the module):
      the resolution matrix — `source`, the exact notice set, and the resolved structure per
      case;
      the extraction goldens, per entry, field-for-field;
      the template branch's no-read property — pass an `entries` value whose consumption would
      raise, and assert the template case still resolves (US1 AS-1);
      freshest-wins on `entries-inconsistent.json`, asserting both the resulting structure
      **and** the `entries_inconsistent` notice;
      `date_ambiguous` on `entries-ambiguous-date.json`, and on `entries-disambiguating.json`
      its **absence** plus the resolved component order propagated to every entry of the pass;
      the malformed-template rows, asserting the fallback structure is the match-recent one and
      not the default;
      the minimal default plus `template_candidate` on `entries-empty.json`;
      the label pass-through property (FR-005) — every block of
      `entries-labeled-causal.json`'s `sections` is byte-identical (`==`, not `in`) in
      `apply_format`'s output, plus the no-content-dropped property for its unmatched-label
      block;
      the **bounded-extraction** property — extend one `entries-consistent.json` entry's body
      in-test with a large filler block containing **no heading line, no line-initial `Label:`
      and no date**, and assert the extracted `Structure` is unchanged from the golden, i.e.
      body length never reaches the extraction output;
      and the FR-003 input-signature property — parse the session-row field names out of
      `skills/session-store/references/schema.md`'s column table **dynamically** (never a
      test-local copy) and assert that set is disjoint from both `FORMAT_INPUT_KEYS` and
      `inspect.signature(resolve_format).parameters`, with a non-vacuity guard that the parsed
      row-field set is non-empty and contains `diary_url`. Comment at the test what
      data-model §9 records: this is an **accepted-weak** gate — the two vocabularies are
      disjoint by ordinary English rather than by construction, and its real value is the
      non-vacuity half.

**Checkpoint**: `make verify` green — US1 independently testable and complete.

---

## Phase 4: User Story 2 — the first write lands and hands back its link (P1)

**Goal**: the adapter interface and the write flow, documented and gated against the mock.

**Independent test**: drive the documented write flow against `bb-mock-mcp` — the append
returns a link, that link is the value handed onward for the row, and the write log shows
exactly one diary append per drafted close.

- [x] T012 [US2] Fill `skills/diary/SKILL.md`'s **interface** section: the two-operation
      skill-level contract `read_recent(n) -> entries[]` (most recent first) and
      `write_entry(content) -> url`, the realization onto the operation contract
      (`write_entry` ≡ `append_entry`, `url` ≡ `link`; `read_recent` keeps its name), the
      `Entry` shape `{link, content, at}` cited to the contract and **not** redefined, and the
      error posture: operation failures surface the contract's uniform error envelope to the
      close flow unchanged — **the adapter attempts and reports honestly; retry policy belongs
      to the close flow**. State that the op-set is closed (append and read, no create), which
      is *why* "never creates diaries" holds — a pin derived from the contract, not an
      aspiration. Reference the diary capability's operations only; name no product and no
      server (FR-006).
- [x] T013 [US2] Fill `skills/diary/SKILL.md`'s **write flow** section: the append targets
      **the team's configured diary through the diary capability** — append-only, no diary
      creation, no alternate destination — and the returned link is what the close flow carries
      into the session row's diary field, the linkage that makes the entry findable from the
      store forever. Say plainly that this is the dual-write's *first* write and that the
      ordering and the failure path (`diary_pending` as the retry queue) are
      `skills/session-store/`'s and the close flow's, cited not restated. Name the deferred
      adapters (Confluence, Notion, git-markdown) as explicitly deferred, and state the FR-4a
      adapter property: swapping diary stores changes bindings, never this skill.
      **This sentence trips the naming scan, so land its mask in the same task.** The merged
      `DENY_PATTERNS` T001 imports bans `confluence` and `notion`, and FR-004 requires naming
      them. Add a deferral-list mask to `tests/contract/test_diary_prose.py` — mask the single
      sentence naming the deferred adapters before the deny scan, the same move
      `test_catalog_prose.py` makes for canonical annotation keys — and pin **both halves**:
      the masked sentence is present and passes, and the same vendor word written anywhere
      *outside* that sentence still fails. Record the reasoning in the module docstring: a
      deferral list states what this adapter does **not** integrate with, which is the opposite
      of the integration-by-name Constitution VII forbids.
- [x] T014 [US2] Fill `skills/diary/SKILL.md`'s **drafting handoff** section per
      data-model.md §7: the inputs the close flow supplies (in-session evidence links; services
      and severity; resolution; the labeled causal proposals; the locally staged pre-upload
      artifact content **including the tool trace and checkpoint history**), and what is not an
      input — **the close-time row update**, since drafting precedes the dual-write, so the row
      state the close writes does not exist when the draft is assembled; the diary skill reads
      no session-row field and writes none.
      **On the timeline, write exactly the narrow claim and no more** (this is the converge
      round's one defended finding): the diary skill **never derives the structured timeline**,
      and where an entry carries a timeline section it is rendered from the same staged sources
      the row's `timeline` field derives from — the tool trace and the checkpoint history. Do
      **not** assert *when* that derivation happens: design §4 places it at close step 4 while
      `commands/close.md` produces it before the dual-write, and asserting either ordering would
      put a second source of truth on a rule slice 5 owns. The claim as written is true under
      both (research R14, and D-23 records the divergence).
      Output is entry content in the resolved format, and causal proposal labels pass through
      format matching **verbatim**: the adapter never strips, rewords, or promotes them
      (Constitution V; the labeling rule itself is slice 5's FR-007).
- [x] T015 [US2] Add `write_entry(invoke, content) -> {"url", "error"}` to
      `tests/helpers/diary_reference.py` — the documented write flow's executable form, so the
      linkage assertion has a **subject**: it calls the `append_entry` operation, returns the
      contract's `link` as `url`, and passes an error envelope through untouched. Without it,
      a test asserting "the returned link is what the row receives" compares a value to itself
      and there is no artifact in between that could hold the transform the assertion claims to
      catch. Comment that it encodes the flow, not a shipped adapter.
- [x] T016 [US2] Write `tests/contract/test_diary_write.py` against `bb-mock-mcp`. It
      **consumes and does not duplicate** slice 1's `tests/contract/test_diary.py`, which
      already gates append→link, `n` validation and the raw error envelope — cite it in the
      module docstring and assert only the consumption layer:
      `write_entry`'s returned `url` is identical to the `link` the mock returned, and is the
      value carried onward to the row's diary field (assert across T015's function, so a
      transform inside it fails the test);
      the mock's write log filtered to the `diary` capability has **length exactly 1** per
      drafted close (SC-004) — the count asserted, not "at least one" — with a docstring line
      recording that the close-*level* ordering claim is gated by slice 5
      (`tests/contract/test_close_flow.py`, `test_lifecycle_full_sim.py`) and that this module
      asserts the adapter's own write;
      the **closed-op-set** pin as an **equality** — the diary ops read from
      `tools/bb-mock-mcp/contract.json` equal exactly `{"append_entry", "read_recent"}`. A
      subset assertion would go quiet in precisely the case that matters, a future
      `create_diary` op, which is the pin FR-004 derives "no diary creation" from;
      and that a failing `write_entry` surfaces the uniform envelope with `op`, `code` and
      `message` all present and `op` naming the diary operation — surfaced, never swallowed.

**Checkpoint**: `make verify` green — US1 + US2 together are the P1 MVP.

---

## Phase 5: User Story 3 — recent entries always arrive newest-first (P2)

**Goal**: the ordering commitment consumed as pinned, with no consumer-side re-sort.

**Independent test**: against the mock (which implements the most-recent-first pin), the
entries used for structure extraction are the n most recent, in order, with no re-sort step
anywhere in the documented flow.

- [x] T017 [US3] Add `consume_recent(entries) -> {"freshest", "considered"}` to
      `tests/helpers/diary_reference.py`: returns `entries[0]` as `freshest` (or `None` when
      empty) and the entries **unchanged** as `considered`. It exists to make "consumed as-is"
      an executable claim rather than a prose one; the comment says that, and says the function
      must never grow a sort.
- [x] T018 [US3] Write `tests/contract/test_diary_ordering.py`. Slice 1's
      `tests/contract/test_diary.py` already gates the mock's raw newest-first behavior,
      short reads and empty reads — cite it in the docstring and assert the consumption layer:
      seed the mock from `entries-consistent.json` by iterating `reversed(entries)` and
      appending each `content` (T003's rule), call `read_recent(5)`, and assert
      `[e["content"] for e in returned]` equals the fixture's content order — the **full
      sequence**, not just the first element, and compared on `content` because the mock mints
      its own `link`/`at`;
      `consume_recent(...)["freshest"]` is the newest entry and `["considered"]` is the
      returned list unchanged (`==` on the whole list);
      short read — seed from `entries-short.json`, `read_recent(5)`, assert both entries come
      back newest-first and resolution proceeds to `source="matched"` (AS-2);
      empty read — `read_recent(5)` returns `[]` and resolution takes the minimal-default path;
      and the **no-reorder source scan**: read `tests/helpers/diary_reference.py`'s source and
      assert the bodies of `extract_structure`, `resolve_format` and `consume_recent` contain
      no `sorted(`, `.sort(` or `reversed(` — scoped to those function bodies by source
      slicing, not the whole file, with a positive control proving the scan can fail. Note
      inline, because the near-collision otherwise reads as a contradiction: the ban is on the
      **encoding** reordering what the contract already ordered; a test module seeding the mock
      oldest-first via `reversed(entries)` is constructing diary state, not consuming a read.

**Checkpoint**: `make verify` green — all three stories complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: the remaining prose gates, the packaging ratchet, and the records this slice owes.
T020–T023 all append to `tests/contract/test_diary_prose.py`, so they are **not** marked `[P]`
— apply them in ID order to keep the diff readable.

- [x] T019 Complete `skills/diary/SKILL.md`'s **non-goals** section: this slice ships prose and
      tests only — no adapter code; the close flow that invokes drafting and executes the
      dual-write is slice 5's, causal labeling of diary drafts is slice 5's FR-007, slice 6
      touches drafts only for untrusted-telemetry delimiting, and `diary_url` / `diary_pending`
      and the write ordering are `skills/session-store/`'s — consumed boundaries, declared and
      cited, never re-implemented (FR-008, Constitution I). Also state the approval boundary
      this slice must not appear to weaken: no write of any kind happens before the responder
      approves the draft, and that gate lives in the close flow.
- [x] T020 Extend the naming scan in `tests/contract/test_diary_prose.py` (T001 landed its
      base): add a **local** pattern `re.compile(r"google\s+docs?", re.IGNORECASE)` on top of
      the shared `DENY_PATTERNS`, following `test_catalog_prose.py`'s local-extension
      precedent. This is load-bearing, not belt-and-braces: the shared list's `google docs`
      pattern does **not** match the singular "Google Doc", which is the exact string design
      §6.2's MVP heading uses and therefore the one most likely to be copied into the new
      skill. Add a **positive control** asserting `"Google Doc"` is rejected, and one asserting
      the shared scan rejects a string it should.
- [x] T021 Add the **operation-fidelity** gate to `tests/contract/test_diary_prose.py`: every
      backtick-quoted single-token span in `skills/diary/**/*.md` that looks like a contract
      operation must be a real operation in `tools/bb-mock-mcp/contract.json`, with the valid
      set built dynamically from that file. **It needs an explicit mask or it fails the prose
      T012 mandates**: the repo's existing predicate
      (`test_skill_capability_naming.py`'s `OP_LIKE_SUFFIXES`) matches any token ending
      `_entry`, so the skill-level name `write_entry` — which FR-001 *requires* the doc to
      state — would be rejected as a non-existent contract op. Declare
      `SKILL_LEVEL_NAMES = {"write_entry"}` as the mask, document its reasoning in the module
      docstring in the house style of `test_skill_capability_naming.py`'s fence-stripping note,
      and pin **both halves** with tests: `write_entry` passes, and a fabricated
      `read_entries` still fails. Record why `read_recent` needs no mask (it is a real contract
      op under both names).
- [x] T022 Add the **ordering-prose** gates to `tests/contract/test_diary_prose.py` (SC-005):
      a positive gate that `references/format.md` states the consumer-side commitment that
      consumers never re-sort; a positive gate that it also states the adapter-side half (an
      adapter over an oldest-first store reverses on read — T008 is what puts that sentence
      there, and without it the mask below is vacuous by construction); and a negative scan for
      consumer-side re-sort directives over an **enumerated** pattern set — at minimum
      `re-sort`, `resort`, `sort the entries`, `reorder`, `oldest first` — masked to permit the
      adapter-side sentence only. Require a two-halved control: the masked sentence is present,
      and masking removes every hit that sentence causes.
- [x] T023 Add the **prose↔encoding agreement** gates to `tests/contract/test_diary_prose.py`:
      the notice kinds named in `references/format.md` and `NOTICE_KINDS` asserted equal **both
      ways**; the four `STRUCTURE_PARTS` likewise named in the doc and asserted both ways (it is
      exported in T005 precisely so it has a gate); the minimal-default skeleton quoted in
      `references/format.md` asserted byte-identical to `MINIMAL_DEFAULT_TEXT`; and the
      two-constant agreement T005 deferred here — `extract_structure(MINIMAL_DEFAULT_TEXT)`
      equals `MINIMAL_DEFAULT` **in full**, every part including `title` and `date_format`
      (data-model §3's pattern-language rule is what makes the skeleton's own title line
      date-bearing, so no part needs a carve-out).
- [x] T024 Add the **packaging ratchet and boundary** gates to
      `tests/contract/test_diary_prose.py` (FR-008): `skills/diary/` contains no `*.py` file,
      and `tests/helpers/diary_reference.py` is named by **no** glob in
      `tests/fixtures/packaging/intended-bundle.json`'s shipped bundle (a direct assertion, not
      an eyeball). Plus the two prose gates `quickstart.md`'s FR map claims and nothing else
      creates: **FR-004** — `SKILL.md` states append-only, no diary creation, no alternate
      destination, and names the deferred adapters; **FR-005** — `SKILL.md` states the drafting
      input contract and that the close-time row update is not among its inputs. Plus the
      non-goals gate: the skill names close-flow ownership of retry and approval, and
      `skills/session-store/`'s ownership of `diary_url` / `diary_pending`, rather than
      restating either. Finally, assert **no `<!-- T0` task marker survives** anywhere under
      `skills/diary/` — the Phase-1 skeleton ships placeholder comments naming the tasks that
      fill each section, and a shipped plugin surface must not carry them once those tasks are
      done.
- [x] T025 Amend `bb-technical-design.md` (research R11): a §6.2 clarification recording that
      the shipped skill abstracts the concrete MVP binding to "the team's configured diary via
      the diary capability" (Constitution VII supersedes the section's concrete framing; the
      binding map makes the store a binding-time fact), that the skill layout is
      `skills/diary/SKILL.md` plus `references/format.md` — extending §3.1's bare
      `diary/SKILL.md` on the `session-store/`/`investigation/` sibling precedent — and the two
      config keys (`battleBuddy.diary.template`, pinned by slice 5, and
      `battleBuddy.diary.recentEntries`, new here, default 5). Add decision-log row **D-23**
      recording this slice's pins with their rationale: read depth 5 behind a config knob; the
      two-case malformed-template definition and its match-recent fallback with the problem
      surfaced; `content` as the sole extraction surface with `at` never read as a date format;
      **the entry title excluded from the compared structure**, with the reason (a per-entry
      title makes every real diary compare inconsistent); the pinned date-token padding rule;
      numeric-date ambiguity resolved pass-level and otherwise **surfaced, never silently
      picked** (the D-22 posture applied to a second surface); consistency detection as what
      makes freshest-wins observable; and format matching as opaque-block arrangement, which is
      what makes the causal-label pass-through a property rather than a promise. Record two
      things honestly alongside the pins: **the timeline-ordering divergence** between §4 step 4
      and `commands/close.md` (this slice asserts neither; research R14), and **R14's three
      deferrals** — `battleBuddy.diary.recentEntries` has no landed reader, the notice
      vocabulary has no landed consumer, and slice 5's `_render_draft_entry` placeholder still
      stands.
- [x] T026 Update `AGENTS.md`: add `skills/diary` to the landed shipped-surface list and mark
      slice 8 complete in the Build order line; keep the file ≤200 lines — it routes, the
      linked documents rule. In the same task, update the slice-8 IOU comment in
      `tests/helpers/lifecycle_flows.py`'s `_render_draft_entry` to cite
      `skills/diary/references/format.md` as the now-landed home of the format-matching rules
      — **a comment/citation change only**: replacing slice 5's stand-in rendering with a real
      format-match is a behavior change to a landed, gated helper and is explicitly out of
      scope (research R14).

**Checkpoint**: `make verify` green; every FR and SC in `quickstart.md`'s map has a passing
gate.

---

## Dependencies

```
Phase 1 (Setup: skill + naming scan + guard registration, fixtures)
   └─> Phase 2 (Foundational: encoding module + constants)   [BLOCKING]
          ├─> Phase 3 (US1) ─┐
          ├─> Phase 4 (US2) ─┼─> Phase 6 (Polish)
          └─> Phase 5 (US3) ─┘
```

- **T001's three parts are one task on purpose.** (a) alone turns `make verify` red via slice
  7's coverage guard; (c) alone without (b) is the rubber stamp that guard's own comment
  forbids.
- **US2 does not depend on Phase 2** in substance (T015 is the only encoding function it adds,
  and it is self-contained), but it is sequenced after it so every story starts green.
- Within Phase 3: T006 → T007 → T009 (resolution consumes extraction and the ambiguity pass) →
  T011. T008 and T010 are authorable alongside them, but T008 also widens the T001 guard and
  supplies the sentence T022's mask needs, so it lands before Phase 6.

## Parallel opportunities

- **T002 ∥ T003** (fixtures vs their README) — once T002's roster is fixed.
- **US1 ∥ US2 ∥ US3** after Phase 2: `references/format.md` + `test_diary_format.py`,
  `SKILL.md` + `test_diary_write.py`, and `test_diary_ordering.py` are disjoint file sets. The
  shared file is `tests/helpers/diary_reference.py` (T006/T007/T009 for US1, T015 for US2,
  T017 for US3) — serialize edits to it.
- Phase 6 has **no** parallel opportunities: T020–T024 all append to one module.

## If scope must be cut

Drop **US3 (P2)**: `consume_recent` (T017), `tests/contract/test_diary_ordering.py` (T018) and
T022's ordering-prose gates go together.

**What does not go with them**: the ordering-consumption *statement* in
`references/format.md` stays under any cut. It is FR-001's ("with its consumer-side corollary
pinned here: consumers never re-sort") and FR-001 is not scoped to US3 — it is authored by
T008, a US1 task, and cutting it would fail a P1 requirement. Never drop a test while keeping
its prose: code without its tests in the same change is incomplete (Constitution VIII). US1 and
US2 are both P1 and neither is cuttable — together they are the MVP. Record any cut in this
file and in the PR body.
