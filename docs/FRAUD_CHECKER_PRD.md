# PRD — Audit Investigation Mode

## Overview

Audit Investigation Mode extends CorpuScan beyond executive financial briefings into an AI-powered forensic investigation assistant.

Instead of transforming financial documents into executive videos, this mode analyzes collections of financial, operational, and legal documents to identify suspicious activity, uncover inconsistencies, and produce evidence-backed investigation reports.

The core principle of this feature is:

> Every conclusion must be traceable to evidence.

The system should never generate a fraud claim without linking it to the exact document, page, and passage that supports the finding.

The AI acts as an investigation assistant that helps auditors discover suspicious patterns, validate hypotheses, and organize evidence. Final decisions remain with human investigators.

Relevant documents include README.md, backend/README.md and frontend/README.md

---

# Problem

Fraud rarely exists inside a single document.

Most financial fraud cases are discovered by combining information from multiple sources:

- invoices
- bank statements
- accounting ledgers
- purchase orders
- contracts
- emails
- financial reports
- company records

A suspicious payment may only become visible when comparing:

- an invoice against a purchase order
- a payment against a bank confirmation
- a vendor against external company information
- financial statements against underlying transactions

Current AI systems can summarize documents quickly, but many fail at the most important requirement for auditing:

**proving where a conclusion came from.**

Auditors need:

- transparent reasoning
- evidence references
- document traceability
- investigation history
- reproducible conclusions

---

# Vision

CorpuScan becomes an AI financial investigation platform capable of exploring large document collections, discovering relationships between entities, and producing evidence-backed fraud investigations.

The system behaves like a forensic investigator:

- reading documents
- creating hypotheses
- following leads
- comparing evidence
- researching external information
- updating fraud likelihood
- documenting every step

---

# Goals

The MVP should:

- ingest large collections of heterogeneous documents
- understand relationships between documents
- investigate suspicious patterns autonomously
- maintain a structured investigation history
- provide evidence-backed findings
- allow auditors to verify every conclusion
- optionally use external intelligence and ML models

---

# Non Goals

The MVP will NOT include:

- legal fraud declarations
- replacing human auditors
- persistent enterprise storage
- authentication
- multi-user collaboration
- automated regulatory reporting
- guaranteed fraud detection

The system identifies suspicious evidence.

Humans determine the final outcome.

---

# Target Users

## External Auditors

Investigate company financial activity efficiently.

## Internal Audit Teams

Analyze suspicious transactions and compliance risks.

## Finance Teams

Validate financial information before reporting.

## Compliance Officers

Review unusual activity and regulatory risks.

---

# Training & Evaluation Dataset

For hackathon development and evaluation, all datasets are stored locally inside: fraud_train_dataset/. all these files correspond to a single company example, so all of them correspond to the same case.


This directory contains the document collections used for training, testing, and validating the investigation pipeline.

The dataset may contain:

- PDFs
- Excel files
- CSV files
- financial reports
- invoices
- purchase orders
- bank statements
- contracts
- emails
- supporting company documents

The ingestion pipeline recursively scans this directory, extracts document content, generates searchable representations, and builds the investigation knowledge base.

Example:

```
fraud_train_dataset/
    ├── invoices/
    ├── bank_statements/
    ├── contracts/
    ├── reports/
    ├── emails/
    └── company_documents/
```

For the hackathon MVP, the dataset is treated as the investigation corpus.

In a production environment, this would be replaced by user uploads or integrations with document management systems.

---

# Ground Truth & Evaluation Reference

The challenge sponsor provides a ground-truth file at `fraud_train_dataset/truth_revealed.md`. This file describes the **known fraud schemes** seeded into the synthetic dataset and serves as the scoring rubric for evaluating investigation accuracy.

## Known Fraud Schemes

### F1 — Fake Vendor (Cash Misappropriation)

A shell vendor **"Ratio Consulting GmbH" (209101)** was created mid-year and received 5 round "Beratung" invoices totalling **€248,000**. No goods receipt exists for any invoice. The vendor was set up, invoiced, and paid by the **same user MV-U05** (broken segregation of duties).

**Detection path:**
- `Kreditoren/Lieferantenbuchungen.txt` → 5 invoices + 5 payments, all round amounts
- `Begleitdokumente/Wareneingangsliste_2025.csv` → no goods receipt for vendor 209101
- `Begleitdokumente/Stammdatenaenderungen_2025.csv` → creator = approver (MV-U05)
- `Begleitdokumente/Berechtigungsauswertung_2025.xlsx` → MV-U05 holds Buchen + Zahlungslauf + Kreditor anlegen

### F2 — Repairs Capitalised as Fixed Assets (Profit Overstatement)

Six repair/maintenance bills (**€150,800 net**) booked as asset additions (accounts 040000/060000) instead of expense 670000. Asset names include "Reparatur", "Instandsetzung", "Austausch", "Generalüberholung". Profit and assets overstated.

**Detection path:**
- `AV/Anlagen.txt` → asset records with repair-type names
- `AV/Anlagenbuchungen.txt` / `Sachkontobuchungen.txt` → acquisitions post to asset accounts, not expense 670000
- Cross-check vendor invoices: invoice describes repair but debit is asset

### F3 — December Costs Parked in January (Cut-off Manipulation)

Eight supplier invoices for December 2025 deliveries (**€192,000 net**) booked in January 2026 and **not accrued** at year-end. Goods received in December with no corresponding 2025 posting. Profit overstated.

**Detection path:**
- `Begleitdokumente/Fakturajournal_Januar_2026_Kreditoren.csv` → invoices with Jan 2026 date but Dec 2025 service date
- `Begleitdokumente/Wareneingangsliste_2025.csv` → matching December goods receipts marked "Rechnung offen"
- `Sachkonten/Sachkontobuchungen.txt` → no 2025 accrual for these items

### F4 — Split Payments Under Approval Limit (Control Breach)

Four payments on **14.10.2025** to vendor **200007 (Castor Papier GmbH)**, each just under €10,000 (9,780 / 9,820 / 9,750 / 9,690 = **€39,040**), to dodge the €10,000 two-signature rule.

**Detection path:**
- `Sachkonten/Sachkontobuchungen.txt` → filter payments by vendor + date, find 4 near-threshold payments same day
- `Begleitdokumente/Pruefungsplanung_JET_2025.docx` → states the €10,000 threshold

## Financial Impact

- F2 + F3 overstate profit by **~€342,800** (reported €2.60m → true ~€2.26m)
- F1 is €248,000 of cash stolen
- F4 is a control breach (no financial misstatement)

## Known Decoys (False Positives to Avoid)

- **D1**: €480,000 machine — real capital investment with Investitionsantrag
- **D2**: "Nord Logistik GmbH" vs "Nordlicht Logistik GmbH" — different VAT-IDs, both with real goods receipts
- **D3**: "Vega Werkstoffe GmbH" (209112) — new mid-year vendor but four-eyes + real deliveries (honest twin of F1)
- **D4**: Year-end volume bonuses — documented rebate
- **D5**: €220,000 Konzernumlage to Austrian parent — related party but disclosed, arm's length
- **D6**: Asset disposal for €1,200 — scrapping of old machine, documented
- **D7**: Invoice + credit note same period (€18,500 each) — normal correction

## Evaluation Scoring

- Top marks: catch **F1** by combining sources + **F2/F3** (profit overstatement pair)
- Bonus: **F4**
- Penalty: accusing any decoy (D1–D7)

---

# User Flow

```
User uploads documents
    ↓
Optional document prioritization
    ↓
Document ingestion
    ↓
Knowledge graph creation
    ↓
Investigation Agent starts
    ↓
DFS investigation loop
    ↓
Investigation buffer generated
    ↓
Evidence-backed final judgement
    ↓
Interactive audit report
```

---

# Supported Documents

The system supports heterogeneous document collections.

Supported formats include:

- PDF
- Excel (.xlsx)
- CSV
- Word documents
- Plain text
- JSON
- Emails
- Financial statements
- Invoices
- Contracts
- Purchase orders
- Bank confirmations

Additional parsers can be added independently.

---

# Document Prioritization

When starting an investigation, users may optionally select documents that they believe are high priority.

Examples:

- suspicious invoices
- unusual transactions
- financial statements
- vendor records

If the user does not specify priorities, the Investigation Agent determines the starting document automatically.

The selection process considers:

- document type
- extracted entities
- financial relevance
- suspicious keywords
- relationships with other documents

---

# Investigation Architecture

The investigation engine is powered by an LLM acting as an autonomous investigator.

The investigator does not simply answer questions.

Instead, it performs an iterative investigation process:

1. Analyze current document
2. Extract relevant evidence
3. Update investigation notes
4. Estimate fraud likelihood
5. Determine next document to investigate
6. Continue until investigation branches are exhausted

The LLM behaves similarly to a forensic auditor following evidence trails.

---

# DFS Investigation Workflow

The investigation follows a Depth First Search strategy over the document relationship graph.

Documents become nodes.

Relationships become edges.

Examples:

```
Invoice
↓
Purchase Order
↓
Bank Payment
↓
Ledger Entry
↓
Financial Statement
```

The investigator follows the strongest lead first.

Example workflow:

```
Start Document
↓
Analyze
↓
Find related documents
↓
Choose strongest lead
↓
Analyze next document
↓
Continue
↓
Dead End
↓
Backtrack
↓
Explore remaining leads
↓
Finish
```

The investigation ends when:

- all relevant branches are explored
- no unexplored relationships remain
- investigation limits are reached

---

# Investigation Buffer

The investigation history is stored as a structured CSV-like buffer.

The purpose of this buffer is to preserve the sequential reasoning history of the investigation.

Each row represents one analyzed document.

Example:

```
doc_id,
notes_summary,
fraud_likelihood,
primary_next_doc,
alt_doc_leads,
open_questions
```

Example entry:

```
invoice_1043.pdf,

Invoice amount differs from ledger by €12,000.
Vendor information matches existing records,
but payment timing is unusual.

,

0.46,

purchase_order_552.pdf,

ledger.xlsx;bank_statement_march.pdf,

Why does the ledger show a different payment amount?
```

The buffer acts as the investigator's memory.

The LLM can revisit previous conclusions, compare evidence, and understand how the investigation evolved over time.

---

# Investigation Agent

The main Investigation Agent is responsible for:

- deciding investigation order
- analyzing documents
- generating hypotheses
- requesting external research
- selecting tools
- updating fraud likelihood
- maintaining the investigation buffer
- generating final conclusions

The agent must always distinguish:

## Evidence

Information directly extracted from documents.

## Hypothesis

A possible explanation based on evidence.

## Conclusion

Final assessment after investigating multiple sources.

---

# Evidence Model

Every finding must contain:

```
Finding

Evidence

Document

Page

Passage

Confidence
```

Example:

```
Finding:

Invoice INV-1043 may have been paid twice.

Confidence:

92%

Evidence:

Invoice.pdf
Page 4

Bank_statement.pdf
Page 8

Ledger.xlsx
Row 120
```


No unsupported finding is allowed.

---

# Tavily MCP Integration

The backend includes a Tavily MCP server as an investigation tool.

The MCP is available internally to the Investigation Agent.

The frontend never communicates directly with Tavily.

The LLM decides when external research is required.

---

# External Intelligence Capabilities

Through Tavily MCP, the investigator can research:

- company history
- corporate ownership
- directors
- regulations
- accounting standards
- similar fraud cases
- previous financial scandals
- legal requirements
- sanctions
- bankruptcy information
- public company information

Example:

Internal finding:

```
Vendor appears suspicious.
```

Agent may query:
```
Vendor name + fraud

Vendor name + bankruptcy

Vendor name + registration

Vendor name + directors
```

External information is always separated from internal evidence.

---

# Optional Fraud Classification Model

The system may include an optional binary classification model.

The model acts as an additional investigation tool.

It does not make decisions.

Example:

Input:

- document embeddings
- financial features
- transaction patterns
- metadata

Output:
```
Fraud Probability:

0.87
```

The Investigation Agent decides whether the prediction is relevant.

The model output is never treated as evidence.

---

# Investigation Tools

The LLM can access:

- Document retrieval
- Semantic search
- Entity extraction
- Relationship discovery
- Tavily MCP
- Regulation search
- Similar fraud research
- Optional fraud classifier

All tool usage is recorded.

---

# Final Investigation Report

After completing the investigation, the system generates a final report.

The report includes:

## Executive Summary

Overview of investigation results.

## Findings

Suspicious activities ordered by severity.

## Evidence

Supporting documents and references.

## Timeline

Chronological reconstruction of events.

## Entity Relationships

Connections between:

- companies
- vendors
- employees
- invoices
- payments
- bank accounts

## Fraud Assessment

Overall likelihood based on investigated evidence.

## Remaining Questions

Unresolved areas requiring human review.

---

# Backend Architecture

Existing CorpuScan infrastructure is reused:

- FastAPI
- Gemini integration
- Tavily integration
- Async jobs
- React frontend
- Progress tracking

New components:
```
backend/
    ├── investigation/
    │
    ├── document_parser/
    │
    ├── embeddings/
    │
    ├── knowledge_graph/
    │
    ├── investigation_agent/
    │
    ├── evidence_store/
    │
    ├── tavily_mcp/
    │
    └── fraud_classifier/
```

---

# Investigation Pipeline

```
Documents
↓
Parsing
↓
Chunking
↓
Embedding
↓
Document Graph
↓
Investigation Agent
↓
DFS Investigation Loop
↓
Investigation Buffer
↓
Evidence Aggregation
↓
Final Report
```

---

# API Endpoints

## POST /investigate

Creates a new investigation.

Input:

- multiple documents
- optional priority documents

Returns:
```
{
job_id
}
```

---

## GET /investigations/{id}

Returns:

- status
- progress
- findings
- investigation history

---

## GET /investigations/{id}/buffer

Returns the investigation CSV-like history.

---

## GET /investigations/{id}/evidence/{id}

Returns:

- document
- page
- highlighted passage

---

# Success Metrics

The MVP is successful if:

- users can upload multiple documents
- the system explores documents autonomously
- investigation history is preserved
- findings include evidence
- auditors can trace conclusions
- external intelligence improves investigations
- suspicious patterns are discovered without excessive false positives

---

# Future Work

Possible improvements:

- OCR support
- Graph database
- Continuous monitoring
- Accounting software integrations
- Human feedback loops
- Advanced fraud models
- Multi-agent investigations
- Automated audit reports
- Regulatory compliance checking

---

# MVP Principles

- Evidence before conclusions.
- Every claim must have a source.
- The AI investigates, humans decide.
- External knowledge is separate from internal evidence.
- Investigation history must be reproducible.
- Transparency is more important than automation.