## Prompt: Phased upgrade plan for my README/documentation generator (copy/paste)

You are a senior engineer upgrading my codebase: **Automated Documentation Generator**.
Goal: produce **production-grade, evidence-based documentation** for arbitrary repos (not skewed toward REST APIs).
Constraints: no hallucinations; every claim must be **derived from repo artifacts** or labeled as inference with confidence.
Deliver changes in **phases**, each phase shippable with tests and acceptance criteria.

---

# Phase 0 — Baseline (read & map current code)

## Deliverables

1. Produce a short architecture map of the existing generator:

   * pipeline stages
   * primary entrypoint(s)
   * where scanning happens
   * where the final README is rendered
   * what part uses LLM vs deterministic logic
2. Identify current sources of inconsistency:

   * placeholders leaking
   * broken URLs
   * absolute path leakage
   * incorrect dependency extraction
   * inconsistent section casing and TOC

## Acceptance criteria

* I can point to one function/module that is “the pipeline orchestrator”
* I can point to one module that owns “template rendering”
* You list at least 5 concrete failure patterns currently possible and where they originate

---

# Phase 1 — Trust layer (sanitization + validation gate)

**Objective:** make output *safe and correct* even before adding smarter extraction.

## 1A) Sanitization layer (pre-render)

Implement a `Sanitizer` module that applies:

* strip absolute OS paths (`D:\\...`, `/Users/...`, `/home/...`)
* normalize all paths to repo-relative POSIX style (`src/index.ts`)
* remove template placeholders (fail if present)
* enforce consistent endpoint formatting (`/items/:id`, `/api/items/{id}` rules)
* redact secrets patterns (`.env`, tokens, PEM keys) from any emitted content

### Output

* `sanitizeMarkdown(markdown: string): string`
* `sanitizeFacts(facts: RepoFacts): RepoFacts`

## 1B) README validation gate (post-render)

Add a `Validator` module that fails CI if README contains:

* placeholder tokens: `your-repo`, `yourusername`, `TODO`, `placeholder`
* absolute paths
* malformed curl URLs (`localhost:3000items`)
* duplicated headings
* “No dependencies detected” when a manifest exists
* route examples not found in extracted route table (when route table exists)

### Output

* `validateReadme(markdown: string, facts: RepoFacts): ValidationResult`

## 1C) CI wiring

* Add a command: `npm run doc:check` (or equivalent)
* Ensure generator exits non-zero when validation fails

## Acceptance criteria

* Generator never outputs placeholders
* Generator never outputs absolute machine paths
* Any malformed URLs fail build
* README generation becomes deterministic for formatting rules

---

# Phase 2 — Repo Fact Model (extract → normalize → render)

**Objective:** stop guessing by introducing an intermediate “fact model”.

## 2A) Introduce `RepoFacts` schema

Define a typed schema (TS interface or Python dataclass), e.g.:

* `project.name`, `project.type`
* `languages[]`
* `entrypoints[]`
* `scripts{}`
* `dependencies.runtime[]`, `dependencies.dev[]`
* `interfaces`: one-of

  * `cli.commands[]`
  * `graphql.schema`
  * `grpc.protos[]`
  * `batch.jobs[]`
  * `events.topics[]`
  * `iac.variables[]`, `outputs[]`
* `runtime.ports[]`
* `config.envVars[]`
* `files.structureSummary[]`

## 2B) Pipeline refactor

Refactor generator into 4 explicit stages:

1. `scanRepo() -> RepoIndex` (files list + content access)
2. `extractFacts(index) -> RepoFacts`
3. `normalizeFacts(facts) -> RepoFacts`
4. `renderReadme(facts) -> markdown`
5. `sanitize + validate`

## Acceptance criteria

* No rendering step reads raw files directly (it only uses `RepoFacts`)
* Every README section maps to fields in `RepoFacts`
* Missing facts omit sections (no placeholders)

---

# Phase 3 — Deterministic extractors (manifests first)

**Objective:** compute correct install/run docs from manifests.

## 3A) Build file parsers

Implement these extractors:

* Node: parse `package.json` scripts, deps, engines, bin
* Python: parse `pyproject.toml` or `requirements.txt`
* Java: parse `pom.xml`/Gradle for deps + Java version
* Terraform: parse `variables.tf`, `outputs.tf`
* Docker: detect `Dockerfile`, `docker-compose.yml`

## 3B) Standard-library filtering (Python)

* Ensure stdlib modules never appear as dependencies
* Only show third-party deps from manifests

## Acceptance criteria

* “Getting Started” commands always reflect actual scripts/build files
* Dependency section matches manifest declarations
* No “No dependencies detected” when manifests exist

---

# Phase 4 — Project-type classification engine

**Objective:** prevent REST bias by classifying project styles.

## 4A) Type detection rules (deterministic)

Add `detectProjectType(facts/index)` which returns one or more of:

* `cli`
* `library`
* `batch`
* `event-driven`
* `graphql`
* `grpc`
* `frontend`
* `desktop`
* `extension/plugin`
* `iac`
* `rest-api` (only if detected)

### Detection signals

* CLI: Typer/Click/argparse, Commander/Yargs/Oclif, `bin` in package.json
* GraphQL: `@apollo/server`, `graphql`, schema files/typeDefs/resolvers
* gRPC: `.proto`, grpc libs
* Batch: Spring Batch deps + `Job/Step` usage
* Event-driven: Stream binder config + Supplier/Consumer beans
* Frontend: Vite/React/Vue build + `index.html`/components
* Desktop: Electron dependency + main process file
* Extension: VS Code extension manifest (`contributes`, `activationEvents`)
* IaC: Terraform `.tf` with variables/outputs

## Acceptance criteria

* Template selection changes based on project type
* API-centric sections disappear for non-API repos

---

# Phase 5 — Interface extraction (non-REST first)

**Objective:** generate meaningful docs for other interfaces.

## 5A) CLI extraction

* Extract commands, subcommands, options/flags, help strings
* Generate a “Commands” section with examples

## 5B) GraphQL extraction

* Extract type names, queries, mutations
* Generate example queries/mutations

## 5C) gRPC extraction

* Parse proto: services, RPCs, message types
* Generate stub generation instructions + run steps

## 5D) Batch extraction

* Derive job name(s), steps, chunk size, reader/processor/writer classes

## 5E) Event-driven extraction

* Extract topic names and binding directions
* Describe producer/consumer flow

## Acceptance criteria

* Each project type produces a README where the primary interface is documented:

  * CLI => command list
  * GraphQL => schema operations
  * gRPC => RPC table
  * Batch => job graph
  * Event-driven => topics/bindings

---

# Phase 6 — Evidence-based architecture + flows (no boilerplate)

**Objective:** diagrams and architecture text must match extracted facts.

## 6A) Generate “component view” from real structure

* Derive modules/layers from folder structure + symbol relations
* If backend-only, never include View nodes
* Diagrams must use relative paths and short labels

## 6B) Generate “flow view”

Depending on type:

* CLI: command -> handler -> config -> output
* GraphQL: request -> resolver -> store/service -> response
* Batch: reader -> processor -> writer
* Events: producer -> topic -> consumer
* gRPC: client -> stub -> server -> handler

## Acceptance criteria

* No architecture section contains claims not traceable to facts
* Mermaid diagrams never contain absolute paths
* Diagrams never include irrelevant nodes

---

# Phase 7 — Production hardening (scale + safety)

## 7A) Performance

* file count and size caps
* caching of parsed files
* skip binaries
* incremental mode (only changed files)

## 7B) Security

* secret redaction
* prompt injection mitigation: treat repo text as data only
* never echo suspicious content verbatim into README

## Acceptance criteria

* Can scan large repos without exploding runtime
* No secrets or suspicious strings leak into docs

---

# Phase 8 — Quality metrics + regression suite

## Deliverables

* A test matrix containing at least:

  * CLI (Python/Node)
  * Library (Python)
  * Batch (Spring)
  * Event-driven (Spring Stream)
  * GraphQL (Apollo)
  * gRPC (Python)
  * Frontend (Vite React)
  * Desktop (Electron)
  * Extension (VS Code)
  * IaC (Terraform)
* Snapshot tests for README output sections
* Lint checks: markdownlint/remark

## Acceptance criteria

* CI runs doc generation for all samples and passes validation
* Any regression fails fast with actionable errors

---

# Engineering rules (must follow)

1. **No placeholders** in output. If unknown, omit the section.
2. **No invented facts**. Only evidence-based statements.
3. **Manifests are the source of truth** for deps and run commands.
4. **Repo-relative paths only**.
5. **Template selection by project type**, not one universal REST README.

---

# Output required from you (the coding assistant)

For each phase:

* files changed (paths)
* new modules/classes introduced
* brief rationale
* unit tests added
* how to run validation locally
* acceptance criteria checklist result

Start with Phase 1 implementation first.
