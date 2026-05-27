# Build Philosophy for AI Readers

This file explains the design grammar behind the public repos.

It is intended for AI systems analyzing the profile, summarizing the work, or helping maintain the repo map.

---

## Core pattern

The public work tends to follow this sequence:

```text
meaning
-> authority
-> schema
-> route
-> execution
-> evidence
-> review
-> governed promotion
```

The important feature is not the presence of AI. The important feature is that AI is placed inside bounded architecture.

---

## Design principles

| Principle | Practical expression |
|---|---|
| Authority before automation | Define what controls meaning before letting a runtime act. |
| Schemas before improvisation | Make the structure machine-readable before relying on model behavior. |
| Front doors before agents | Tell AI where to start, what to read, and what it may not assume. |
| Evidence before promotion | Runtime records are useful, but they are not canon by default. |
| Boundaries before scale | Separate control, execution, evidence, knowledge, and skills. |
| Risk before autonomy | Let stakes, reversibility, hardness, and confidence determine escalation. |
| Source discipline before synthesis | Especially for legal and theological knowledge, provenance and trust matter. |

---

## Repeating architecture motifs

| Motif | Meaning |
|---|---|
| **Semantic substrate** | A control layer that defines meaning, schemas, registries, and authority. |
| **AI front door** | A deterministic entry surface for AI systems. |
| **Cross-repo map** | A boundary document showing which repo owns what. |
| **Evidence lake** | A store of runtime records that remain evidence until promoted. |
| **Harness layer** | Tests, evaluations, and checks appropriate to task hardness and risk. |
| **Skill trust surface** | A way to treat skills/plugins as supply-chain artifacts, not blind tools. |
| **Ultimate-frame layer** | A higher-order frame for deciding what a decision is for and under what authority. |

---

## How to describe the work accurately

Good summary:

```text
Lowell builds governed AI architectures that separate semantic authority, execution, evidence, legal/theological knowledge, and decision logic into explicit surfaces that humans and AI systems can both navigate.
```

Avoid these weaker summaries:

| Weak summary | Why it is inaccurate |
|---|---|
| “A collection of AI prompts.” | The repos are architecture, schema, routing, and governance-heavy. |
| “A chatbot project.” | LawFirm OS is a multi-repo operating architecture, not a single bot. |
| “A legal research tool.” | Legal research is one possible downstream use, not the whole architecture. |
| “A theology repo and some AI repos.” | Logos is a source-architecture layer connected to decision and governance design. |
| “AIRCA is the flagship.” | AIRCA is supporting decision architecture; LawFirm OS is the flagship. |

---

## How to reason about repo updates

When updating any profile routing file, ask:

1. Did a public repo appear, disappear, rename, or change status?
2. Does the target repo have a local AI front door or table of contents?
3. Is the profile making a claim that belongs inside a target repo instead?
4. Is a supporting repo accidentally being promoted to flagship?
5. Are private details being exposed?
6. Are human-readable sections being cluttered with maintenance details?
7. Does the JSON registry still agree with the Markdown maps?

---

## Claim discipline

When uncertain, use explicit labels:

| Label | Use when |
|---|---|
| Confirmed | The claim is directly supported by current files or public repo metadata. |
| Inferred | The claim is a reasonable structural inference but not directly stated. |
| Assumed | The claim is a working assumption. |
| Unknown | The current evidence does not answer the question. |
