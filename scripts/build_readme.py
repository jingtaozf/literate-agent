"""Regenerate the LP README entry points across edo-literate.

Three artefacts in one script:

  1. Root ``README.org`` — the human-facing front door.
  2. ``lp/<group>/README.org`` for every group under ``lp/`` — per-
     submodule entry with Why / What / How files relate / Read order /
     full index.
  3. (Already lives in ``scripts/build_index.py``; this script does NOT
     touch ``lp/INDEX.org`` — invoke that script separately.)

Per-group narrative metadata is held in ``GROUP_NARRATIVE`` below. To
adjust an elevator pitch, file-role mapping, or read-order: edit the
metadata dict and re-run. The per-file alphabetical index at the bottom
of each README is auto-rebuilt from each .org file's ``#+TITLE``.

The root README's table of submodules is grouped into three buckets
declared in ``ROOT_BUCKETS`` so a senior engineer can scan by role.

Usage:
    uv run python scripts/build_readme.py            # rebuild all
    uv run python scripts/build_readme.py --check    # diff vs disk, exit 1 if drift

Companion: ``scripts/build_index.py`` for ``lp/INDEX.org``, and
``scripts/audit_lp.py`` for the file-level A-grade audit.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parent.parent
LP_ROOT = REPO_ROOT / "lp"

# ────────────────────────────────────────────────────────────────────
# Per-group narrative metadata — hand-curated.
#
# Each entry has:
#   elevator    — one-paragraph "what this submodule is" (10-20 lines).
#   groups      — [(label, role)] conceptual grouping for "How files
#                 relate"; empty list ⇒ single-file submodule.
#   read_order  — bulleted reading sequence for a senior engineer
#                 landing on the README.
#
# To add a new submodule: append a new key here. The renderer will
# pick it up. (lp/<new-group>/ also needs to exist on disk.)
# ────────────────────────────────────────────────────────────────────

GROUP_NARRATIVE: dict[str, dict] = {
    "automated-skill-management": {
        "elevator": (
            "=automated-skill-management= (ASM) is the *backend* that owns "
            "the weekly-cycle pipeline for skill curation: detects drift in "
            "the shipped skill catalog, applies the validated proposal, and "
            "reconciles the result back to the wisdom graph. Runs as a "
            "FastAPI server + APScheduler worker behind k8s CronJobs; talks "
            "to its own Postgres schema (``asm.proposals``, "
            "``asm.apply_jobs``, ``asm.skill_health``) and reads PCR's "
            "graph schema via the imported ``pcr_skill_networking`` library."
        ),
        "groups": [
            ("=core.org=", "FastAPI server, observability wiring, weekly "
                          "cycle orchestrator, reconcile loop, the apply "
                          "pipeline's shared scaffolding."),
            ("=apply.org=", "Apply pipeline — turns an approved proposal "
                           "into a graph mutation; idempotency, retries, "
                           "audit."),
        ],
        "read_order": [
            "=_project.org= — subsystem overview (the imported "
            "architecture docs).",
            "=core.org= → FastAPI app + cycle orchestrator first; this is "
            "the entry point a reader meets when running ``make server``.",
            "=apply.org= — drill into the mutation pipeline once you know "
            "where it gets called from.",
        ],
    },
    "mega-claude-release": {
        "elevator": (
            "=mega-claude-release= holds the release-engineering scripts "
            "and assets for shipping the ``mega-claude`` CLI wrapper (the "
            "shell tool that drives Claude Code with a LiteLLM proxy for "
            "non-Claude-Max users). Small repo — almost all of the actual "
            "code lives in =mega-ui/cli/= and the build pipeline. This LP "
            "layer just captures the version bumps + signing helpers."
        ),
        "groups": [],
        "read_order": [
            "Single .org for now (=core.org=). See ``mega-ui/`` for the "
            "consumer of these release artefacts.",
        ],
    },
    "mega-code": {
        "elevator": (
            "=mega-code= is the mega-code Claude Code plugin (the encrypted "
            "``.mgep`` bundle that =mega-ui= ships) plus the data-collection "
            "client that uploads session-level skill telemetry to "
            "=mega-code-server=. Python stack — Claude Code hooks + "
            "statusline + pipeline that extracts skills from intercepted "
            "tool-use events."
        ),
        "groups": [
            ("=client.org=", "The data-collection client itself: hooks "
                            "(collector, statusline), CLI install/uninstall, "
                            "session schema + I/O."),
            ("=pipeline.org=", "Skill / strategy extraction pipeline that "
                              "consumes captured events and emits the "
                              "wisdom graph payloads."),
            ("=server.org=", "Light-weight FastAPI server that receives "
                            "uploaded sessions and forwards to the "
                            "persistent skill store."),
            ("=scripts.org=", "Operator scripts (install, status, manual "
                             "trigger)."),
            ("=tests.org=", "Unit + integration tests across the client + "
                           "pipeline."),
        ],
        "read_order": [
            "=_project.org= — what the plugin does end-to-end.",
            "=client.org= → the hooks are the entry surface; everything "
            "else fans out from them.",
            "=pipeline.org= — the extraction logic that consumes the "
            "client's emitted events.",
            "=server.org= — only relevant if you're deploying or upgrading "
            "the upload endpoint.",
        ],
    },
    "mega-code-infra": {
        "elevator": (
            "=mega-code-infra= is the Terraform + k8s configuration for the "
            "mega-code platform on AWS EKS (Seoul region, account "
            "198116961614). Provisions the EKS cluster, RDS Postgres, S3 "
            "caches, Bitbucket pipeline runners, and every k8s "
            "Deployment / Service / Ingress for the platform's running "
            "services. Tagged releases (=v0.1.X=) drive "
            "Bitbucket-pipeline-triggered ``terraform apply``."
        ),
        "groups": [
            ("=foundation.org=", "VPC, EKS, RDS, S3, IAM — the cluster baseplate."),
            ("=workloads-platform.org=", "mega-code-server + mega-code-web "
                                        "+ mega-service k8s manifests."),
            ("=workloads-skill.org=", "skill-scout-server + skill-enhance-server "
                                     "+ pcr-skill-networking + skill-encryption "
                                     "k8s manifests."),
            ("=workloads-asm.org=", "automated-skill-management k8s manifests."),
            ("=observability.org=", "Phoenix tracing, CloudWatch dashboards, "
                                   "OAuth2 OTLP forwarder."),
            ("=cluster.org=", "EKS addons, k8s namespace bits."),
            ("=data-stores.org=", "RDS + ElastiCache."),
            ("=network.org=", "VPC, security groups, ACM."),
            ("=envs.org=", "Dev / prod tfvars split."),
            ("=values.org=", "Helm values overrides."),
            ("=secrets.org=", "AWS Secrets Manager wiring."),
            ("=variables.org=", "Top-level Terraform variables + tfvars schema."),
            ("=pipeline.org=", "Bitbucket pipeline definition (plan→apply "
                              "gate for dev + prod)."),
        ],
        "read_order": [
            "=_project.org= — design / deployment runbook overview.",
            "=foundation.org= → cluster baseplate before reading workloads.",
            "=workloads-*.org= — pick the workload you're debugging.",
            "=pipeline.org= — only when changing CI / release shape.",
        ],
    },
    "mega-code-oss": {
        "elevator": (
            "=mega-code-oss= is the open-source mirror of =mega-code='s "
            "plugin client — same data-collection hooks but with the "
            "proprietary extraction bits stripped, so external Claude Code "
            "users can drop it into their workflow without taking the "
            "mega-* binary dependency. Kept in sync with =mega-code= via "
            "periodic ``/lp-resync mega-code-oss`` passes."
        ),
        "groups": [
            ("=client.org=", "Hooks (collector, statusline) + CLI + session "
                            "I/O — same shape as mega-code/client.org but "
                            "with fewer integrations."),
            ("=pipeline.org=", "The slimmed extraction pipeline."),
            ("=server.org=", "Stub server for local-only development."),
            ("=scripts.org=", "Operator scripts."),
            ("=tests.org=", "Test suite mirrored from mega-code/tests/."),
        ],
        "read_order": [
            "=_project.org= — what's stripped vs the proprietary mirror.",
            "Read in the same order as ``mega-code/``, knowing the surface "
            "is smaller.",
        ],
    },
    "mega-code-web": {
        "elevator": (
            "=mega-code-web= is the public-facing Next.js 15 app for "
            "megacode.ai — marketing landing pages, demo flow, comparison "
            "tables, admin console (behind oauth2-proxy). React 19 + "
            "Tailwind. Some routes do server-rendered analytics; some are "
            "pure SSG. Embeds 3 massive auto-generated graph-data .ts "
            "files (~85k LOC) that drive the demo visualisations."
        ),
        "groups": [
            ("=app-marketing.org=", "=src/app/(marketing)/= — landing, "
                                   "features, blog, comparison, benchmarks "
                                   "(~33k lines)."),
            ("=app-admin.org=", "=src/app/(admin)/= — graph viewer, API "
                               "keys, usage, dashboard, billing, my-page."),
            ("=app-demo.org=", "=src/app/(demo-run)/= — interactive demo path."),
            ("=app-misc.org=", "=src/app/{auth,login,api,404}/= + =src/proxy.ts="),
            ("=components.org=", "Shared UI primitives + marketing widgets."),
            ("=lib.org=", "Helpers + types + API client."),
            ("=scripts.org=", "Operator + CI scripts."),
            ("=tests.org=", "Vitest + Playwright."),
        ],
        "read_order": [
            "=_project.org= — short architectural overview.",
            "=app-marketing.org= → it's where ~70% of the file count is.",
            "=app-admin.org= → drill in for the admin console.",
            "=components.org= / =lib.org= → reference as you read pages.",
        ],
    },
    "mega-service": {
        "elevator": (
            "=mega-service= is the *auth + identity + billing* API for the "
            "mega-code platform. FastAPI; owns user accounts, GitHub/Google "
            "OAuth, API key issuance, subscription / usage accounting, and "
            "transactional email. Not the LLM-serving path — that's "
            "mega-code-server. Read this when you need to know who someone "
            "is and what they're allowed to do."
        ),
        "groups": [
            ("=auth.org=", "OAuth flows (GitHub + Google), refresh-token "
                          "rotation, session model."),
            ("=users.org=", "User model + account-management endpoints."),
            ("=api_keys.org=", "API key issuance + revocation + per-key budgets."),
            ("=usage.org=", "Token usage tracking + monthly aggregation."),
            ("=jobs.org=", "Subscription billing job + Stripe webhook handlers."),
            ("=admin.org=", "Admin endpoints for support / on-call use."),
            ("=email.org=", "Transactional email (Postmark) — verify, "
                           "reset, billing notifications."),
            ("=system_llm_keys.org=", "Per-tier system-LLM key allocation."),
            ("=tests.org=", "Pytest suite for the above."),
        ],
        "read_order": [
            "=_project.org= — what this owns vs mega-code-server.",
            "=auth.org= → OAuth + session is the entry surface for every "
            "other endpoint.",
            "=users.org= → next, since identity hangs off this.",
            "=api_keys.org= + =usage.org= — the value-flow "
            "(request → billable token) reads from these.",
        ],
    },
    "mega-ui": {
        "elevator": (
            "=mega-ui= (Cargo crate name =mega-ide=) is the local-only "
            "optimization studio: a Rust daemon (~43 .rs / ~30k LOC) that "
            "spawns the host's =claude= CLI with an encrypted plugin "
            "bundle, plus an embedded Next.js frontend (36 .tsx + 15 .ts / "
            "~12k LOC) the daemon serves to the user's browser at "
            "=http://127.0.0.1:<port>/=. Runs entirely on the user's "
            "machine; data never leaves."
        ),
        "groups": [
            ("=daemon.org=", "Whole Rust =src/= tree (recursive) — main "
                            "daemon, claude spawn, hybrid router, LiteLLM "
                            "proxy, persistence ledger, axum routes."),
            ("=build.org=", "=build.rs= — embeds the Next.js static export "
                           "into the Rust binary at compile time."),
            ("=frontend-app.org=", "Next.js app router — landing + nested "
                                  "=p/[id]/{connect,setup,run,result}= "
                                  "per-project routes."),
            ("=frontend-components.org=", "20+ React UI components."),
            ("=frontend-hooks.org=", "=useSession= + =useStatusLine=."),
            ("=frontend-lib.org=", "API client, types, small pure helpers."),
            ("=resources.org=", "Bundled =sitecustomize.py=."),
        ],
        "read_order": [
            "=_project.org= — daemon + frontend topology + LP layer slicing.",
            "=daemon.org= → =src/main.rs= section first (it's the boot "
            "path), then =src/state.rs=, then drill into routes / "
            "session_runtime.",
            "=frontend-app.org= → start at =layout.tsx= and =page.tsx=, "
            "then per-project nested routes.",
            "=frontend-components.org= / =frontend-lib.org= → reference "
            "as the pages dictate.",
        ],
    },
    "pcr-admin-ui": {
        "elevator": (
            "=pcr-admin-ui= is the Next.js admin console that ties together "
            "PCR (wisdom graph + skill networking), Scout (auto-ingest of "
            "external skill catalogs), and ASM (automated skill management "
            "proposals). One frontend reads three backend APIs and presents "
            "a unified admin view."
        ),
        "groups": [
            ("=app.org=", "Top-level =src/app/= routes — layout, home, "
                         "common navigation."),
            ("=asm.org=", "ASM routes — proposals, apply jobs, decisions "
                         "queue, ingest run details."),
            ("=scout.org=", "Scout routes — ingest runs, cycle drill-down, "
                           "approval queue, settings."),
            ("=components.org=", "Shared UI primitives + ASM/Scout-specific "
                                "components."),
            ("=lib.org=", "API clients (one per backend), shared helpers."),
            ("=tests.org=", "Vitest + Playwright."),
        ],
        "read_order": [
            "=README.org= (this file) — entry point.",
            "=app.org= → layout + navigation give the routing topology.",
            "=asm.org= or =scout.org= — pick the backend you're touching.",
            "=components.org= / =lib.org= — reference as needed.",
        ],
    },
    "pcr-skill-networking": {
        "elevator": (
            "=pcr-skill-networking= is the *router + wisdom-graph store* "
            "that sits between the skill catalog and downstream consumers. "
            "Owns the wisdom graph schema (entities, relations, "
            "embeddings), multi-source skill federation (skills.sh, "
            "skillsmp, github topics, …), a feedback path for retraining "
            "signals, and a routing engine that picks the right skill for "
            "a query. Python; uses Postgres + an embedding cache."
        ),
        "groups": [
            ("=core.org=", "Top-level package files: config, domain, "
                          "protocols, factory."),
            ("=wisdomgraph.org=", "Graph store — local JSON-LD backend + "
                                 "Postgres backend, schema, migrations."),
            ("=router.org=", "Wisdom-router orchestrator: query → "
                            "candidate skills → ranking → response."),
            ("=parser.org= / =validator.org= / =reasoner.org= / "
             "=retriever.org=",
             "Pipeline stages — parse input, validate against schema, "
             "reason over the graph, retrieve embeddings."),
            ("=curator.org=", "Quality gates + dedup before write."),
            ("=feedback.org=", "Feedback ingestion + Postgres feedback store."),
            ("=utils.org=", "Cross-cutting utilities: tracing, embedding "
                           "cache, metrics."),
            ("=client.org=", "Stand-alone client SDK — used by mega-code "
                            "plugin; intentionally has no internal imports "
                            "so it can be shipped client-side."),
            ("=server.org=", "FastAPI server wrapping the router."),
            ("=engine.org=", "Compatibility shim for old =pcr_engine= callers."),
            ("=tests.org=", "Pytest suite."),
        ],
        "read_order": [
            "=_project.org= — long-form architecture.",
            "=wisdomgraph.org= → the data model is the foundation.",
            "=router.org= → orchestration on top of the graph.",
            "=parser / validator / reasoner / retriever .org= — open in "
            "pipeline order as needed.",
            "=client.org= last — thin surface, depends on the protocol "
            "in =core.org=.",
        ],
    },
    "py-foundation": {
        "elevator": (
            "=py-foundation= is the Python utility library every mind-ai "
            "backend pip-installs by git tag "
            "(``wisdom_graph_utils@vX.Y.Z``). Provides: SQLite-backed LLM "
            "call cache, OpenTelemetry tracing wiring, OAuth2 OTLP "
            "exporter, multi-provider LLM client baseline (Anthropic + "
            "OpenAI + Gemini), pricing lookup, FastAPI bearer-auth "
            "helpers, Postgres advisory-lock helper. Heavy deps lazy-load "
            "so a light consumer (mindagent, gepa, auto_adaptor) pays no "
            "import cost."
        ),
        "groups": [
            ("=core.org=", "Top-level files: =__init__.py= public "
                          "re-exports, =_config.py= runtime config "
                          "singleton, =_version.py=."),
            ("=caching.org=", "=SqliteObjectCache= — process-local "
                             "memoisation for expensive LLM/embedding "
                             "calls."),
            ("=tracing.org=", "OpenAI SDK auto-tracing + cost-tracking "
                             "instrumentation."),
            ("=observability.org=", "OTel tracer-provider helpers, OAuth2 "
                                   "OTLP exporter (mainly for Phoenix)."),
            ("=llm.org=", "Multi-provider LLM client baseline + per-token "
                         "pricing snapshot."),
            ("=utils.org=", "Shared utilities: cache backends, "
                           "cancellation, embedding cache, S3 helpers, "
                           "similarity index, step-logger, tracing."),
            ("=api.org=", "FastAPI helpers — =BearerAuth= for JWT + "
                         "API-key dual auth, OpenAPI security-scheme "
                         "stamping (opt-in [api] extra)."),
            ("=db.org=", "Postgres helpers — =advisory_lock= context "
                        "manager (opt-in [db] extra)."),
            ("=examples.org=", "Runnable examples (caching, OAuth2 OTLP, "
                              "tracing)."),
        ],
        "read_order": [
            "=README.org= (this file) — top-down overview.",
            "=core.org= → start at =__init__.py= so you see the public "
            "re-export surface; then =_config.py=.",
            "=caching.org= → simplest concrete component; read it to "
            "learn the LP style used here.",
            "=llm.org= → the heaviest subpackage.",
            "=tracing.org= + =observability.org= → wire-up patterns every "
            "consumer copies.",
        ],
    },
    "skill-encryption": {
        "elevator": (
            "=skill-encryption= is the *dual-stack* repo that protects "
            "mega-* skills: a 14-crate Rust toolchain (~30k LOC under "
            "=src/crates/=) for format / encrypt / decrypt / pack / sign "
            "primitives + a CLI (=mega-code= crate), plus a Python FastAPI "
            "backend (=backend/src/mega_backend/= / ~9.5k LOC) that brokers "
            "encryption keys via a gateway. Producer side (encrypt) runs "
            "in CI / dev; consumer side (decrypt) runs inside mega-ui's "
            "daemon."
        ),
        "groups": [
            ("=rust-crypto.org=", "Core crypto crates: =mega-crypto= + "
                                 "=mega-core= + =mega-proto= (key "
                                 "derivation, AEAD primitives, wire format)."),
            ("=rust-format.org=", "Format crates: "
                                 "=mega-{agent,script,skill}-format= + "
                                 "=mega-publish-env=."),
            ("=rust-encrypt.org=", "Encrypt crates — producer pipeline."),
            ("=rust-decrypt.org=", "Decrypt crates — consumer pipeline "
                                  "(mega-ui side)."),
            ("=rust-mega-code.org=", "=mega-code= CLI crate (largest single "
                                    "crate)."),
            ("=rust-tests.org=", "Cross-crate Rust integration tests."),
            ("=backend-core.org=", "Backend top-level: config, db, errors, "
                                  "main + dev gateway."),
            ("=backend-api-auth.org=", "API routes + auth middleware."),
            ("=backend-services.org=", "Crypto services, repositories — "
                                      "the brokerage layer."),
            ("=backend-models-schemas.org=", "Pydantic schemas + SQLAlchemy "
                                            "models."),
            ("=backend-tests.org=", "Pytest suite + integration fixtures."),
        ],
        "read_order": [
            "=_project.org= — producer / consumer split + encryption "
            "threat model.",
            "=rust-crypto.org= → primitives first.",
            "=rust-format.org= → on what format do we operate.",
            "=rust-encrypt.org= → producer pipeline.",
            "=rust-decrypt.org= → consumer pipeline (mega-ui calls this).",
            "=backend-*.org= — only when touching the key brokerage.",
        ],
    },
    "skill-enhance-server": {
        "elevator": (
            "=skill-enhance-server= is the upgrade pipeline that takes raw "
            "SKILL.md packages (often discovered by Scout) and runs them "
            "through LLM-based enhancement: synthesise missing prose, "
            "infer metadata, dedupe near-duplicates, score quality, and "
            "write back an enhanced version to the catalog. "
            "APScheduler-driven; uses Postgres for job tracking and S3 "
            "for artefact storage."
        ),
        "groups": [
            ("=api.org=", "FastAPI surface — trigger / status / cancel."),
            ("=scheduler.org=", "APScheduler wrapper + Postgres-backed "
                               "leader election + scanner tick."),
            ("=workers.org=", "Worker pool — runs the actual enhancement "
                             "pipeline per job."),
            ("=clients.org=", "External-service clients (skills.sh, "
                             "skillsmp, GitHub topics)."),
            ("=llm.org=", "LLM call wrappers — prompts + retry policy."),
            ("=storage.org=", "Postgres + S3 storage interfaces."),
            ("=reuse.org=", "Dedup / near-duplicate detection."),
            ("=result.org=", "Result writer + post-enhancement validation."),
            ("=obs.org=", "OTel tracing + structured logging."),
            ("=scripts.org=", "Operator scripts."),
            ("=tests.org=", "Pytest suite."),
        ],
        "read_order": [
            "=_project.org= — end-to-end flow narrative.",
            "=scheduler.org= → leader election + scanner is how jobs land.",
            "=workers.org= → the actual enhancement loop.",
            "=llm.org= + =clients.org= — the LLM + external-API parts.",
            "=result.org= + =reuse.org= — what happens after a job finishes.",
        ],
    },
    "skill-scout-server": {
        "elevator": (
            "=skill-scout-server= is the *auto-ingest engine* that crawls "
            "the open ecosystem (skills.sh, skillsmp, GitHub topics, "
            "HuggingFace Hub) and surfaces candidate skills for human "
            "approval. Multi-stage pipeline (step1..step7) with explicit "
            "gates between stages. Python + FastAPI + Postgres; the most "
            "mature LP repo in this meta-repo (10% prose / 73% code — "
            "the LP authoring reference)."
        ),
        "groups": [
            ("=core.org=", "Top-level files: config, domain, protocols, "
                          "packaging, cli, factory."),
            ("=pipeline.org=", "Pipeline orchestrator + per-step modules "
                              "(step1..step7)."),
            ("=gates.org=", "Gating cascade (Gate1, Gate2, Gate3)."),
            ("=repositories.org=", "External-source adapters."),
            ("=store.org=", "Persistence (SQLite today, Postgres later)."),
            ("=reporter.org=", "Per-cycle reporter (HTML + JSON summary)."),
            ("=ingest.org=", "Bulk ingest CLI + FastAPI runner."),
            ("=eval.org=", "Pipeline evaluation harness."),
            ("=api.org=", "HTTP API surface."),
            ("=utils.org=", "Cross-cutting utils."),
            ("=prompts.org=", "YAML prompt files (no Python)."),
            ("=experiments.org=", "Throwaway experiments under "
                                 "=experiments/scripts/=."),
            ("=scripts.org=", "Operator + CI scripts."),
            ("=tests/*.org=", "Tests by tier (e2e / integration / unit*)."),
        ],
        "read_order": [
            "=project.org= — full architecture.",
            "=pipeline.org= → step1..step7 in order; this is the spine.",
            "=gates.org= → between-step gates that decide what proceeds.",
            "=repositories.org= → external sources are the inputs.",
            "=reporter.org= → the operator-facing output.",
            "=tests/= — dense and a great way to learn the boundaries.",
        ],
    },
}

# ────────────────────────────────────────────────────────────────────
# Root README — three buckets group the 14 submodules by role.
# ────────────────────────────────────────────────────────────────────

ROOT_BUCKETS = [
    ("Skill-platform backbone", [
        "pcr-skill-networking",
        "skill-scout-server",
        "skill-enhance-server",
        "skill-encryption",
        "automated-skill-management",
    ]),
    ("Product surface", [
        "mega-code",
        "mega-code-oss",
        "mega-ui",
        "mega-claude-release",
        "mega-code-web",
        "pcr-admin-ui",
    ]),
    ("Platform / shared", [
        "mega-service",
        "mega-code-infra",
        "py-foundation",
    ]),
]


# ────────────────────────────────────────────────────────────────────
# Renderers
# ────────────────────────────────────────────────────────────────────


def _read_title(f: Path) -> str:
    for line in f.read_text().splitlines()[:20]:
        m = re.match(r"^#\+TITLE:\s*(.+?)\s*$", line)
        if m:
            return m.group(1)
    return ""


def collect_lp_files(grp_dir: Path) -> list[tuple[str, str]]:
    """Return [(filename, #+TITLE)] for every .org in the group dir
    (recursing into a single ``tests/`` subdir for skill-scout-server).
    Excludes README.org itself and underscore-prefixed scratch files."""
    out: list[tuple[str, str]] = []
    for f in sorted(grp_dir.iterdir()):
        if f.is_dir() and f.name == "tests":
            for sub in sorted(f.iterdir()):
                if (sub.name.startswith(("#", "_"))
                        or sub.suffix != ".org"
                        or sub.name.endswith("~")):
                    continue
                out.append((f"tests/{sub.name}", _read_title(sub)))
            continue
        if (f.name.startswith(("#",))
                or f.suffix != ".org"
                or f.name.endswith("~")
                or f.name == "README.org"):
            continue
        out.append((f.name, _read_title(f)))
    return out


def render_group_readme(grp: str, info: dict, lp_files: list[tuple[str, str]]) -> str:
    elevator = info["elevator"]
    groups = info["groups"]
    read_order = info["read_order"]

    if groups:
        how_block = "\n\n".join(f"- {label} — {role}" for label, role in groups)
    else:
        how_block = "(single file — see the index below.)"

    read_block = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(read_order))

    index_lines = []
    for fname, ftitle in lp_files:
        if ftitle:
            index_lines.append(f"- [[file:{fname}][{fname}]] — {ftitle}")
        else:
            index_lines.append(f"- [[file:{fname}][{fname}]]")
    index_block = "\n".join(index_lines) if index_lines else "(empty)"

    return f"""\
# -*- Mode: POLY-ORG; indent-tabs-mode: nil;  -*- ---
#+TITLE: {grp} — LP entry point
#+OPTIONS: tex:verbatim toc:nil \\n:nil @:t ::t |:t ^:nil -:t f:t *:t <:t
#+STARTUP: noindent

* Table of Contents                                            :noexport:TOC:

* Why this file exists

Entry-point document for ``lp/{grp}/``. A senior engineer landing here
should be able to: (1) understand what this submodule is, (2) know
which file owns which subsystem, (3) pick a sensible read order. For
deeper architectural prose see ``_project.org`` in this folder; for
the file-by-file index scroll to the bottom of this README.

* What this submodule is

{elevator}

* How files relate

{how_block}

* Read order for newcomers

{read_block}

* LP files (full index)

Auto-generated from each ``.org``'s ``#+TITLE``. Regenerate via
``scripts/build_readme.py``.

{index_block}
"""


def render_root_readme() -> str:
    """Render the root README.org with three-bucket submodule table."""
    bucket_blocks = []
    for bucket_name, members in ROOT_BUCKETS:
        rows = []
        for grp in members:
            if grp not in GROUP_NARRATIVE:
                continue
            # First sentence of elevator → root-table cell
            first = GROUP_NARRATIVE[grp]["elevator"].split(". ")[0].rstrip(".")
            # Strip the leading =grp= label if it duplicates the row name
            first = re.sub(rf"^=*{re.escape(grp)}=*\s+(?:is\s+)?", "", first)
            first = first[:1].upper() + first[1:] if first else ""
            rows.append(
                f"| [[file:lp/{grp}/README.org][={grp}=]] | {first} |"
            )
        bucket_blocks.append(
            f"** {bucket_name}\n\n"
            "| Submodule | Elevator |\n"
            "|-----------+----------|\n"
            + "\n".join(rows)
        )
    submodules_section = "\n\n".join(bucket_blocks)

    return f"""\
# -*- Mode: POLY-ORG; indent-tabs-mode: nil;  -*- ---
#+TITLE: edo-literate — literate-programming meta-repo
#+OPTIONS: tex:verbatim toc:nil \\n:nil @:t ::t |:t ^:nil -:t f:t *:t <:t
#+STARTUP: noindent

* Table of Contents                                            :noexport:TOC:

* Why this file exists

You're looking at the *front door* of =edo-literate=. A senior
engineer landing on the repo root (GitHub, Bitbucket, or =cd= into
the checkout) should be able to leave this page with three things
settled: (1) what this repo is, (2) which submodule owns the problem
they came for, and (3) where to read next. Every word below is here
for that job; the file ends with explicit "read next" pointers so
the trail keeps going.

* What edo-literate is

=edo-literate= is the *literate-programming meta-repo* for the
mind-ai backend ecosystem. Every line of production source for the
submodules under =repos/= is authored as prose-first Org-mode under
=lp/<sub>/*.org=, then tangled back into the matching submodule's
Python / TypeScript / Rust / Terraform files. Read the .org for the
*why*; the tangled file exists for tooling that doesn't speak Org.

Three concrete things follow from that:

1. *Source of truth is =lp/<sub>/*.org=.* The tangled files in
   =repos/<sub>/= are regenerated by ``make tangle FILE=…`` and
   must not be hand-edited by AI agents — a PreToolUse hook
   (=.claude/hooks/block-tangled-edit.sh=) rejects every
   ``Edit/Write/MultiEdit`` against the tangled extensions
   (=.py=, =.ts=, =.tsx=, =.rs=, =.tf=) under =repos/<sub>/=. The
   only carve-out is =alembic/versions/*.py= which alembic owns.

2. *Two index files matter.* =README.org= (this file) is the
   *human-readable* entry. =lp/INDEX.org= is the
   *machine-regenerated* per-file index across every group, with
   elevator pitches and tangle-target paths. Read this first to
   pick a submodule; open =lp/INDEX.org= when you want the full
   flat catalogue.

3. *Cross-submodule design lives in =lp/draft.org= →
   =lp/decisions-log.org=.* Open proposals queue + accepted /
   rejected archive + research notes — same lifecycle every
   submodule uses.

* How submodules relate

{len(GROUP_NARRATIVE)} submodules, organised by the role they play in the platform:

{submodules_section}

* Read order for newcomers

If you have nowhere specific to start, this sequence will get you
oriented in ~30 minutes:

1. *This file* — front-door overview (you're here).
2. =CLAUDE.md= — the agent-only layer at the root: hard rules,
   hooks, risk → autonomy gates. Skim once even if you're a human.
3. =lp/INDEX.org= — auto-generated catalogue. Scroll past the
   elevator pitches into the per-group section that matches your
   target.
4. =lp/<group>/README.org= — per-submodule entry. Each one follows
   the same shape: *Why → What this submodule is → How files
   relate → Read order → Full index*. The "Read order" line is
   the one to obey.
5. =lp/<group>/_project.org= — deeper architectural prose where
   present (subsystem-level overview; not every group has one
   yet).
6. =lp/<group>/<file>.org= — the individual literate source.
   Tangles to =repos/<group>/<…>=. Edit *here*, never the tangled
   file.

For agent sessions, also load:
- =.claude/rules/*.md= — auto-imported by Claude Code at session
  start; they encode literate-org discipline + LP autonomy levels +
  per-submodule conventions lifted from the submodule's own rules.

* Top-level Org files

Files at =lp/= root, outside any submodule:

- [[file:lp/INDEX.org][lp/INDEX.org]] — auto-generated cross-submodule index, with one
  elevator pitch per group + per-file tangle targets. Regenerated by
  ``make build-index``.
- [[file:lp/draft.org][lp/draft.org]] — open design proposals queue (cross-cutting).
- [[file:lp/decisions-log.org][lp/decisions-log.org]] — accepted / rejected design proposals +
  research notes (timeline).

* Build + lint commands

#+begin_src bash
make tangle FILE=lp/<sub>/<x>.org    # tangle one .org back to repos/<sub>/
make tangle-repo REPO=<sub>           # every .org in one submodule
make tangle-all                       # every non-underscore lp/**/*.org

make check-structure                  # depth ≤ 5, prose-before-src, no grab-bag
make build-index                      # regenerate lp/INDEX.org
make build-readme                     # regenerate root README.org + lp/<group>/README.org
make build-tangle-map                 # refresh .cache/tangle-map.tsv

uv run python scripts/audit_lp.py     # file-level A-grade audit + per-construct gap report
#+end_src

Post-format runs the matching submodule's =make format= (or =npm run
format=, or =uvx ruff format=) automatically after each tangle,
scoped to the touched submodule. Disable with =NO_POST_FORMAT=1= for
bulk patches; skip per-submodule via =POST_FORMAT_SKIP=… in the
Makefile.

* Coding rules

Every cross-cutting rule lives under =.claude/rules/*.md= and is
auto-loaded into agent sessions started at the meta-repo root.
Per-submodule rules live under each =repos/<sub>/.claude/rules/=
and ride with that submodule's solo-launch sessions; the
cross-cutting subset has been lifted into the meta-repo's
=.claude/rules/= with a submodule-suffix in the filename to keep
scope explicit.

Highest-leverage rules to skim first:

- =literate-programming-document-first.md= — the prose-before-code
  rule (the *single most important* style rule in this tree)
- =lp-autonomy-levels.md= — L2 / L3 / L4 risk gates per LP surface
- =lp-purge-deleted-files-first.md= — handling upstream-deleted
  files during =/lp-resync= without resurrecting them
- =always-work-on-jt-branch.md= — branch discipline across submodules
- =no-tests-via-evalElisp.md= — don't run test suites through the
  Emacs MCP tool (it blocks the editor)

See =CLAUDE.md= for the rest, including hook registrations and the
auto-imported per-submodule CLAUDE.md cascade.

* Where this file fits in the LP-style audit

The same rubric every =lp/**/*.org= file is graded against
(file-local-vars Mode line, =#+TITLE=, =* Why=, =* Table of Contents
:noexport:TOC:=, module-section prose) applies to this README too —
this file is the *root entry point* and must pass the same A-grade
check as the per-submodule READMEs. Run =uv run python
scripts/audit_lp.py= to confirm. Per-construct (=A+= tier) prose
isn't relevant here — there are no =:LITERATE_ORG_MODULE:= sections
in this file.
"""


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────


def _write_or_check(path: Path, content: str, check_only: bool) -> bool:
    """Return True if content matches disk (or was written)."""
    if check_only:
        existing = path.read_text() if path.is_file() else ""
        if existing == content:
            return True
        print(f"DRIFT: {path.relative_to(REPO_ROOT)}")
        diff = difflib.unified_diff(
            existing.splitlines(), content.splitlines(),
            fromfile=f"a/{path.name}", tofile=f"b/{path.name}", lineterm="",
        )
        for line in list(diff)[:30]:
            print(f"    {line}")
        return False
    path.write_text(content)
    print(f"wrote: {path.relative_to(REPO_ROOT)}")
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Don't write; exit 1 if any README would change.",
    )
    args = parser.parse_args(argv[1:])

    ok = True

    # Per-group READMEs
    for grp, info in sorted(GROUP_NARRATIVE.items()):
        grp_dir = LP_ROOT / grp
        if not grp_dir.is_dir():
            print(f"SKIP (missing): {grp}")
            continue
        lp_files = collect_lp_files(grp_dir)
        content = render_group_readme(grp, info, lp_files)
        ok &= _write_or_check(grp_dir / "README.org", content, args.check)

    # Root README
    ok &= _write_or_check(REPO_ROOT / "README.org", render_root_readme(), args.check)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
