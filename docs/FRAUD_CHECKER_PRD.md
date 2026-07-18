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