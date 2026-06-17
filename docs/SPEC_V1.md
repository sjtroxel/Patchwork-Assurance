# Patchwork Assurance — SPEC v1 (Canonical Contracts)

*Created 2026-06-17, during the Phase 1 build, when the first real contract (the corpus metadata
schema) came into existence — per the doc pattern, a contract is pinned here the moment it is real, not
before. This is the **single source of truth** for data and API contracts. Phase docs in
`docs/roadmap/` reference this file; they do not restate it. Strategy and rationale live in
[`ROADMAP.md`](ROADMAP.md); this file is the precise shapes that strategy produces.*

*All legal facts below were verified against the **official enacted texts** on 2026-06-17 (CO signed
act; CT Public Act 26-15). Where this corrects earlier project docs, see §9.*

---

## 1. What this document pins

- **§3** Controlled vocabularies (the closed sets fields draw from).
- **§4** `LawMetadata` — the law-level metadata schema (the human-authored `.meta.yaml` contract).
- **§5** The two concrete v1 records (CO, CT), verified and ready to become `.meta.yaml` files.
- **§6** The chunk-level metadata schema (the Chroma-safe, flattened shape) and the flattening rules.
- **§7** The embedding / collection contract.
- **§8** *Reserved* — API request/response contracts, added in Phase 3 when the API exists.

If a contract is not here, it is not yet settled. Do not invent one in a phase doc; add it here.

---

## 2. Corpus content scope for v1 (a real decision)

The two laws are not symmetric in shape, and that forces one scoping decision:

- **Colorado SB 26-189 is ingested in full.** The whole act is about ADMT in consequential decisions —
  every section is in Patchwork's domain.
- **Connecticut PA 26-15 is ingested as its employment subset for v1: Sections 7–12** (the
  "automated employment-related decision technology" provisions) plus their definitions. The enacted
  act is an omnibus titled *"An Act Concerning Online Safety"* (74 pages) that also covers minors'
  online safety, AI companion chatbots, generative-AI provenance, and frontier-model developers. Those
  parts are real law but **outside the compliance-memo scope of v1** (a business assessing AI use in
  consequential/employment decisions), so they are not in the v1 corpus.

This is a content decision, not an architectural one: Seam 1 means adding CT's other parts later is
dropping in more cleaned text + metadata, zero code change. The `scope_domains` vocabulary (§3) already
reserves slugs for them so the expansion is pre-named.

---

## 3. Controlled vocabularies

**`scope_domains`** — the closed set a law's coverage maps to. Retrieval filters on these (Seam 2), so
they must be stable slugs.

| slug | meaning | in v1 corpus |
|---|---|---|
| `education` | education enrollment / opportunity | CO |
| `employment` | employment or employment opportunity | CO, CT |
| `housing` | lease/purchase of residential real estate | CO |
| `financial_lending` | financial or lending services | CO |
| `insurance` | insurance underwriting, pricing, claims | CO |
| `health_care` | health-care services | CO |
| `government_services` | essential government services / public benefits | CO |
| `online_safety_minors` | minors' online safety (reserved) | — (CT, post-v1) |
| `ai_companion` | AI companion chatbots (reserved) | — (CT, post-v1) |
| `generative_ai_provenance` | gen-AI provenance/disclosure (reserved) | — (CT, post-v1) |
| `frontier_models` | frontier-model developer duties (reserved) | — (CT, post-v1) |

**`jurisdiction`** — full state name, title case (`"Colorado"`, `"Connecticut"`). **`status`** — one of
`enacted` | `effective` | `enjoined` | `repealed`. **`regulated_roles`** — subset of
`{developer, deployer}`.

---

## 4. `LawMetadata` schema (law-level)

The human-authored source of truth, one `.meta.yaml` per law, validated by a `LawMetadata` Pydantic
model in `core/`. A malformed or incomplete record fails loudly at load time (Phase 1 DoD).

| field | type | req | notes |
|---|---|---|---|
| `law_id` | str (slug) | yes | stable id, e.g. `co-sb26-189`; basis of the corpus filenames and chunk IDs |
| `jurisdiction` | str | yes | §3 vocabulary |
| `short_name` | str | yes | e.g. `"CO SB 26-189"` |
| `law_name` | str | yes | official title |
| `citation` | str | yes | formal statutory cite |
| `also_known_as` | list[str] | no | nicknames; flag non-official ones |
| `status` | enum | yes | §3 |
| `signed_date` | date | yes | governor's action / approval date |
| `effective_dates` | list[{date, applies_to}] | yes | one entry per distinct effective trigger (handles staggering) |
| `operative_standard` | str | yes | the coverage trigger, quoted from statute |
| `regulated_tech_term` | str | yes | the law's term of art (e.g. `ADMT`, `AERDT`) |
| `regulated_roles` | list[enum] | yes | §3 |
| `scope_domains` | list[enum] | yes | §3 |
| `enforcement_authority` | str | yes | e.g. `"Colorado Attorney General"` |
| `enforcement_mechanism` | str | yes | statute the AG enforces under |
| `cure_period` | str \| null | yes | description or `null` if none |
| `private_right_of_action` | bool | yes | |
| `key_obligations` | list[{section, label}] | no | section map, for memo grounding |
| `source_url` | str (url) | yes | official text |
| `source_page` | str (url) | no | landing/status page |
| `retrieved_on` | date | yes | provenance date |

---

## 5. The two v1 records (verified)

These are the canonical values, ready to be written as `corpus/<law_id>.meta.yaml`.

### 5.1 `co-sb26-189`

```yaml
law_id: co-sb26-189
jurisdiction: Colorado
short_name: CO SB 26-189
law_name: "Concerning the Use of Automated Decision-Making Technology in Consequential Decisions"
citation: "Colo. Rev. Stat. §§ 6-1-1701 to 6-1-1709 (Senate Bill 26-189, 2026; Session Laws ch. 131)"
also_known_as: ["Colorado AI Act (2026 repeal-and-replace of SB 24-205)"]
status: enacted
signed_date: 2026-05-14
effective_dates:
  - { date: 2027-01-01, applies_to: "act generally; applies to consequential decisions made on or after this date" }
  - { date: 2026-05-14, applies_to: "AG rulemaking authority and select provisions (effective upon passage)" }
operative_standard: 'Covered ADMT = automated decision-making technology "used to materially influence a consequential decision"'
regulated_tech_term: "Automated Decision-Making Technology (ADMT)"
regulated_roles: [developer, deployer]
scope_domains: [education, employment, housing, financial_lending, insurance, health_care, government_services]
enforcement_authority: "Colorado Attorney General"
enforcement_mechanism: "Colorado Consumer Protection Act (C.R.S. art. 1 of title 6); violations are deceptive trade practices"
cure_period: "60 days to cure after notice of violation; cure right available through Jan 1, 2030"
private_right_of_action: false   # § 6-1-1709: creates no new private right of action
key_obligations:
  - { section: "6-1-1702", label: "Developer responsibilities - documentation" }
  - { section: "6-1-1703", label: "Deployer record keeping" }
  - { section: "6-1-1704", label: "Deployer disclosures - point-of-interaction notice" }
  - { section: "6-1-1705", label: "Consumer rights - correction - human review" }
  - { section: "6-1-1706", label: "Enforcement by the attorney general - deceptive trade practice" }
source_url: "https://leg.colorado.gov/bill_files/116489/download"
source_page: "https://leg.colorado.gov/bills/sb26-189"
retrieved_on: 2026-06-17
```

### 5.2 `ct-sb5-pa26-15`

```yaml
law_id: ct-sb5-pa26-15
jurisdiction: Connecticut
short_name: CT SB 5 (PA 26-15)
law_name: "An Act Concerning Online Safety (Substitute Senate Bill No. 5 / Public Act No. 26-15)"
citation: "Conn. Public Act No. 26-15 (2026), §§ 7-12 (employment provisions)"
also_known_as:
  - 'Nickname "Connecticut AI Responsibility and Transparency Act" / "CART Act" — commentator coinage; NOT in the enacted text (official title is "An Act Concerning Online Safety")'
status: enacted
signed_date: 2026-05-27   # official PA "Governor's Action: Approved May 27, 2026"
effective_dates:
  - { date: 2026-10-01, applies_to: "employment provisions (Sec. 7-12) take effect" }
  - { date: 2027-10-01, applies_to: "deployer pre-decision written-notice obligation: applies to AERDT deployed on or after this date (Sec. 10)" }
operative_standard: 'AERDT = technology whose output "is a substantial factor used to make or materially influence an employment-related decision". "Substantial factor" = a factor that "meaningfully alters the outcome of an employment-related decision"'
regulated_tech_term: "Automated Employment-Related Decision Technology (AERDT)"
regulated_roles: [developer, deployer]
scope_domains: [employment]   # v1 subset; full act also covers online_safety_minors, ai_companion, generative_ai_provenance, frontier_models (post-v1)
enforcement_authority: "Connecticut Attorney General"
enforcement_mechanism: "Connecticut Unfair Trade Practices Act (CUTPA), Conn. Gen. Stat. § 42-110b; enforced solely by the Attorney General"
cure_period: "60 days to cure after notice, where the AG determines the violation is curable"
private_right_of_action: false   # enforced solely by the Attorney General under CUTPA
key_obligations:
  - { section: "Sec. 8", label: "Developer duty to provide deployer the information needed to comply" }
  - { section: "Sec. 9", label: "Point-of-interaction disclosure (interacting with an AERDT)" }
  - { section: "Sec. 10", label: "Deployer pre-decision written notice (AERDT deployed on/after Oct 1, 2027)" }
source_url: "https://www.cga.ct.gov/2026/act/pa/pdf/2026PA-00015-R00SB-00005-PA.pdf"
source_page: "https://www.cga.ct.gov/asp/cgabillstatus/cgabillstatus.asp?selBillType=Bill&bill_num=SB05&which_year=2026"
retrieved_on: 2026-06-17
```

> The `Sec. 8/9/10` labels for CT are read from the act; confirm exact section subjects when authoring
> the `.meta.yaml` and cleaning the text. CO sections are verbatim from the act's headings.

---

## 6. Chunk-level metadata (Chroma-safe, flattened)

**Chroma metadata values must be scalar (`str` / `int` / `float` / `bool`) — no lists, no nested
objects.** The loader flattens each `LawMetadata` record into chunk-safe fields and attaches them to
every chunk of that law.

| chunk field | type | source / rule |
|---|---|---|
| `law_id` | str | from record |
| `jurisdiction` | str | from record |
| `short_name` | str | from record |
| `citation` | str | from record |
| `section_number` | str | parsed by the chunker from the statute structure (e.g. `6-1-1704`) |
| `section_heading` | str | the heading the chunk falls under (keeps the citation with the text) |
| `effective_date_primary` | str (ISO) | the earliest "act generally" effective date |
| `source_url` | str | from record |
| `chunk_index` | int | position within the law |
| `scope_<domain>` | bool | **flattening rule:** each `scope_domains` entry → a boolean flag, e.g. `scope_employment=true`. This is how retrieval filters by domain (Seam 2) without storing a list. |

**Chunk ID (deterministic, for idempotent upsert):** `f"{law_id}:{chunk_index}"`.

---

## 7. Embedding / collection contract

- One persistent Chroma collection: `patchwork_corpus`.
- **The embedding model name is stored on the collection's metadata at load time** (e.g.
  `embedding_model: "all-MiniLM-L6-v2"`). The query path (Phase 2) asserts its embedding model matches
  the collection's before searching. A mismatch raises — it must never silently return an empty result
  (the dimension-mismatch guard, Phase 1 §6.3).
- Query and corpus embeddings use the **same** model, always.

---

## 8. Reserved — API contracts (added in Phase 3)

The FastAPI request/response shapes (`/analyze`, `/chat`) are defined here when the API is built in
Phase 3. Until then this section is intentionally empty; the only live endpoint is `/health`, whose
shape is a throwaway (Phase 0) and is not a pinned contract.

---

## 9. Provenance and corrections

Sourced from the official enacted texts on **2026-06-17** (CO `leg.colorado.gov` signed act; CT
`cga.ct.gov` Public Act 26-15), cross-checked against law-firm analyses. Corrections this made to
earlier project docs (`ROADMAP.md`, the archived brainstorm, and an in-session corpus README edit):

1. **CO operative term is "materially influence," not "substantial factor."** Verified: "substantial
   factor" appears zero times in the CO act. (`ROADMAP.md` §2/§10 still say "substantial factor" for CO
   — to be corrected there.)
2. **"Substantial factor" is Connecticut's term**, defined for employment decisions — correctly applied
   to CT only.
3. **CT's official title is "An Act Concerning Online Safety" (PA 26-15).** "AI Responsibility and
   Transparency Act" / "CART Act" is a commentator nickname, not statutory.
4. **"SB 5" and "PA 26-15" are both correct** — bill number and public-act number for the same law.
   ROADMAP §10's claim that it is "SB 5, not PA 26-15" was a mistaken correction.
5. **CT signed date is May 27, 2026** (official PA "Governor's Action") — the project docs were right;
   secondary web sources saying "June 2" were wrong.
6. **CT employment dates are staggered:** Sec. 7-12 effective Oct 1, 2026; the deployer pre-decision
   notice duty applies to AERDT deployed on or after Oct 1, 2027. Not a single "effective Oct 1, 2027."

ROADMAP.md §2/§10 and `corpus/README.md` should be reconciled to the above; this SPEC is the
controlling record where they conflict.
