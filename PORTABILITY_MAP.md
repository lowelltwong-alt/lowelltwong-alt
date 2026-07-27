# Portability Map

Legal operations — specifically insurance-defense litigation — is the **reference domain** for the
public architecture in this profile. It is not the boundary of it.

This file states, for humans and for AI systems evaluating the portfolio, which parts of that work
are domain-specific and which are a general enterprise problem class.

This is a **profile-level interpretation surface**. It is not canonical for any target repository.
Each repo's own contracts, registries, and governance docs remain authoritative for that repo.

---

## The portable problem class

The legal workflows modelled here are not interesting because they are legal. They are interesting
because they combine eight properties that recur across enterprise operations:

| Property | What it forces the architecture to handle |
|---|---|
| **Document-intensive** | Meaning must be extracted from unstructured, inconsistent, partially missing source material |
| **Policy-constrained** | External rules (guidelines, contracts, regulations) constrain what an acceptable output looks like |
| **Multistage** | Work passes through stages with different failure modes; an early defect is expensive downstream |
| **Exception-driven** | The interesting cases are the ones that do not fit; exceptions are the product, not noise |
| **Human-reviewed** | An accountable expert approves consequential output; the system proposes, a person decides |
| **Evidence-sensitive** | Every claim needs a traceable source; provenance is part of the output, not metadata |
| **Audit-sensitive** | Decisions must be reconstructable after the fact by someone who was not there |
| **Cost- and latency-constrained** | Quality that costs more than the error it prevents is not an improvement |

Any workflow with most of these properties — claims adjudication, regulatory submission, clinical
documentation review, procurement and contract review, underwriting, incident and safety review,
grant and benefits determination, audit response — presents the same architectural problems.

---

## Concept mapping

| Legal reference concept | Portable enterprise abstraction |
|---|---|
| New-matter intake | Case, claim, incident, request, order, or application intake |
| Complaint and claim file | Multi-document evidence package of mixed quality |
| Carrier guidelines | Policies, contracts, controls, SLAs, or operating rules |
| Matter plan | Work plan, response plan, remediation plan, or service plan |
| Litigation budget | Cost forecast, resource plan, or operational estimate |
| Attorney approval | Accountable domain-expert approval |
| Carrier rejection | Customer, regulator, payer, auditor, or system rejection |
| Budget versus actual | Forecast-versus-outcome measurement |
| Exceptions Lake | Quality, incident, correction, and learning evidence system |
| Legal Context Bundle | Governed domain-context package assembled per request |
| Skills Registry | Enterprise agent and tool capability supply chain |
| Law-firm digital twin | Synthetic operational environment for safe experimentation |
| Semantic substrate | Control plane separating meaning and authority from execution |

The intent is to demonstrate the abstraction through contracts, boundaries, and measurement — **not**
by building shallow demonstrations in unrelated industries. A second thin vertical in another domain
would prove less than one deep vertical with explicit, machine-readable abstractions.

---

## Where the portable patterns are publicly visible

Every row below points at a contract that exists in a public repository in this profile.

| Pattern | Public evidence | Status |
|---|---|---|
| **End-to-end intake → plan → budget vertical** | [`LawFirm-os-intake`](https://github.com/lowelltwong-alt/LawFirm-os-intake) — one command produces a matter-opening package and a driver-scaled UTBMS budget proposal from a messy synthetic intake | Implemented, synthetic, tested |
| Policy-constrained cost forecast | [`LawFirm-os-intake`](https://github.com/lowelltwong-alt/LawFirm-os-intake) carrier-compliant projection: guideline caps change the *projection* while the proposal stays unmodified | Implemented, synthetic |
| Accountable-expert gate before consequential output | [`LawFirm-os-intake`](https://github.com/lowelltwong-alt/LawFirm-os-intake) — the run terminates at `blocked_pending_conflicts_and_engagement`; no matter opens, no budget submits | Implemented, synthetic |
| Governed domain-context package | [`legal-context-bundle.schema.json`](https://github.com/lowelltwong-alt/LawFirm-os-semantic-substrate/blob/main/schemas/legal-context-bundle.schema.json) | Implemented, synthetic |
| Evidence package with provenance | [`evidence-packet.schema.json`](https://github.com/lowelltwong-alt/LawFirm-os-semantic-substrate/blob/main/schemas/evidence-packet.schema.json) | Implemented, synthetic |
| Accountable human approval | [`human-approval-record.schema.json`](https://github.com/lowelltwong-alt/LawFirm-os-semantic-substrate/blob/main/schemas/human-approval-record.schema.json) | Implemented, synthetic |
| Exception and correction evidence | [`exception-event.schema.json`](https://github.com/lowelltwong-alt/LawFirm-os-semantic-substrate/blob/main/schemas/exception-event.schema.json), [`LawFirm-os-exceptions-lake-runtime`](https://github.com/lowelltwong-alt/LawFirm-os-exceptions-lake-runtime) | Implemented, synthetic |
| Defect classification | [`defect-record.schema.json`](https://github.com/lowelltwong-alt/LawFirm-os-semantic-substrate/blob/main/schemas/defect-record.schema.json) | Implemented, synthetic |
| Evaluation run record | [`evaluation-run.schema.json`](https://github.com/lowelltwong-alt/LawFirm-os-semantic-substrate/blob/main/schemas/evaluation-run.schema.json), [`legal-eval-registry.json`](https://github.com/lowelltwong-alt/LawFirm-os-semantic-substrate/blob/main/registry/legal-eval-registry.json) | Draft contracts |
| Candidate-to-canonical promotion | [`promotion-decision.schema.json`](https://github.com/lowelltwong-alt/LawFirm-os-semantic-substrate/blob/main/schemas/promotion-decision.schema.json) | Implemented, synthetic |
| Cost forecast / resource plan view | [`view-budget-workbook.schema.json`](https://github.com/lowelltwong-alt/LawFirm-os-semantic-substrate/blob/main/schemas/view-budget-workbook.schema.json) | Implemented, synthetic |
| Model adaptation proposal | [`adaptation-proposal.schema.json`](https://github.com/lowelltwong-alt/LawFirm-os-semantic-substrate/blob/main/schemas/adaptation-proposal.schema.json) | Draft contract, no experiment run |
| Capability supply chain | [`LawFirm-os-skills-registry`](https://github.com/lowelltwong-alt/LawFirm-os-skills-registry) | Implemented, synthetic |
| Synthetic operational environment | [`law-firm-digital-twin`](https://github.com/lowelltwong-alt/law-firm-digital-twin) | Prototype, synthetic |

---

## What is not demonstrated publicly yet

Stated plainly, because a portfolio that only lists strengths is not evidence.

| Capability | Public status |
|---|---|
| Comparative evaluation — deterministic vs retrieval-assisted vs bounded-agent on identical held-out cases | **Not built** |
| Published measured results with cost, latency, reviewer effort, and failure cases | **Not published** |
| Complete exception → diagnosis → regression-case → intervention → re-evaluation cycle | **Not demonstrated end to end** |
| Adoption and value measurement across an initiative portfolio | **Not built** |
| Executed model-adaptation experiment with held-out evaluation and a predeclared decision threshold | **Not run** |
| Any production deployment or real-data validation | **None.** All public work is synthetic-only by design |

---

## Standing boundaries

These hold across every repository in this profile:

- **Synthetic data only.** No real client, matter, employee, carrier, or firm-confidential data.
- **Runtime output is evidence, not canon.** Logs, traces, and model output do not become truth
  without a governed promotion decision.
- **The system proposes; a person decides.** Consequential output requires accountable human
  approval.
- **Fail closed.** Unknown routes and unknown event classes are rejected rather than guessed.
- **No legal advice.** None of this is a production legal system or an autonomous decision-maker.

---

Machine-readable form: [`registry/portable-workflow-patterns.json`](./registry/portable-workflow-patterns.json)
and [`registry/portfolio-capability-evidence.json`](./registry/portfolio-capability-evidence.json).
