# PRD — Cognee Knowledge Memory Layer Integration

## Overview

This feature introduces **Cognee** as the knowledge memory and relationship intelligence layer for CorpuScan Audit Investigation Mode.

The existing Audit Investigation Mode already provides:

- heterogeneous document ingestion
- LLM-powered forensic investigation
- DFS-based investigation workflow
- investigation buffer
- Tavily MCP external intelligence
- evidence-backed conclusions
- optional fraud classification signals

However, fraud investigations depend heavily on discovering hidden relationships across many documents.

Fraud rarely exists inside one isolated file.

A suspicious pattern may only become visible when connecting:

- invoices
- vendors
- employees
- payments
- bank transactions
- permissions
- contracts
- accounting entries
- emails

Cognee is added as the **investigation memory layer** responsible for building and maintaining a connected representation of the company information.

The core principle:

> The LLM investigates. Cognee remembers and connects. Evidence proves the conclusion.

---

# Motivation

The current investigation architecture relies on:

- document retrieval
- LLM reasoning
- manually generated relationships

This works for small investigations but becomes weaker when relationships are distributed across many documents.

Example:

Document 1:

```
Invoice:

Vendor:
Ratio Consulting GmbH

Amount:
€50,000
```

Document 2:

```
User permissions:

MV-U05

Can create vendors

Can approve payments
```

Document 3:

```
Goods receipt:

No receipt exists for vendor 209101
```

A human auditor immediately connects:

```
MV-U05

    |
    |
created

    |
    |

Vendor 209101

    |
    |
issued

    |
    |

Invoices

    |
    |
paid without

    |
    |

Goods Receipt
```

The important information is not contained in one document.

The relationship between documents is the evidence trail.

---

# Goals

The Cognee integration should:

- create a company knowledge representation
- discover relationships between entities
- improve Investigation Agent context
- provide graph-based investigation paths
- improve document prioritization
- reduce unnecessary document analysis
- enable visual investigation graphs
- preserve evidence traceability

---

# Non Goals

Cognee will NOT:

- decide whether fraud occurred
- replace the Investigation Agent
- replace the investigation buffer
- replace evidence storage
- generate final audit conclusions
- act as a source of truth

Cognee provides connected knowledge.

The LLM provides reasoning.

Auditors provide final judgement.

---

# Architecture Change

## Previous Architecture

```
Documents

↓

Parsing

↓

Investigation Agent

↓

DFS Investigation

↓

Investigation Buffer

↓

Final Report
```

---

## New Architecture

```
Documents

↓

Document Processing

↓

Cognee Knowledge Layer

        |
        |
        ├── Entity Extraction
        |
        ├── Knowledge Graph
        |
        ├── Vector Memory
        |
        └── Relationship Discovery


↓

Investigation Agent

↓

DFS Investigation

↓

Investigation Buffer

↓

Evidence Aggregation

↓

Final Report
```

---

# Cognee Responsibilities

Cognee becomes responsible for creating the investigation knowledge base.

## 1. Document Memory

Cognee stores contextual knowledge extracted from:

- PDFs
- Excel files
- CSV files
- Word documents
- emails
- financial statements
- invoices
- contracts
- purchase orders
- bank confirmations

---

## 2. Entity Extraction

Cognee identifies relevant entities.

Examples:

```
Company

Ratio Consulting GmbH


Employee

MV-U05


Vendor ID

209101


Transaction

€248,000


Account

040000
```

---

## 3. Relationship Discovery

Cognee creates connections between entities.

Example:

```
Employee MV-U05

        |
        |
created

        |
        |

Vendor 209101

        |
        |
generated

        |
        |

Invoice Documents

        |
        |
paid through

        |
        |

Bank Transactions
```

---

## 4. Semantic Memory

Cognee provides semantic retrieval.

The Investigation Agent can ask:

```
Find everything related to vendor 209101.
```

or:

```
What entities are connected to suspicious payments?
```

or:

```
Show relationships between employees and vendors.
```

---

# Integration With Investigation Agent

The Investigation Agent gains access to Cognee as a tool.

Existing tools:

- Document retrieval
- Evidence lookup
- Tavily MCP
- Fraud classifier

New tools:

- Knowledge search
- Entity relationship lookup
- Investigation graph traversal

---

# Investigation Workflow Update

## Previous DFS Flow

```
Current document

↓

Find related documents

↓

Choose next document

↓

Analyze

↓

Repeat
```

---

## New DFS Flow

```
Current document

↓

Query Cognee

↓

Retrieve entities and relationships

↓

Generate investigation branches

↓

Select strongest lead

↓

Analyze next document

↓

Update investigation buffer

↓

Repeat
```

---

# Example Investigation

Input:

```
20 company documents
```

---

Cognee creates:

```
Ratio Consulting GmbH

        |
        |
Invoices

        |
        |
Payments

        |
        |
MV-U05

        |
        |
Permissions
```

---

Investigation Agent receives:

```
Potential relationship:

Vendor 209101

Connected employee:

MV-U05

Reason:

Same user created vendor
and approved payments.
```

---

Agent decides:

```
fraud_likelihood:

0.82

next_document:

Berechtigungsauswertung.xlsx
```

---

Investigation buffer:

```
doc_id:
Berechtigungsauswertung.xlsx

notes_summary:
MV-U05 has both vendor creation and payment approval permissions.

fraud_likelihood:
0.82

primary_next_doc:
Wareneingangsliste.csv

alt_doc_leads:
Lieferantenbuchungen.txt

open_questions:
Were goods received for vendor 209101?
```

---

# Relationship Between Cognee and Investigation Buffer

The two systems have different purposes.

## Cognee

Answers:

```
What does the system know?
```

Stores:

- entities
- relationships
- semantic memory
- document connections

---

## Investigation Buffer

Answers:

```
What did the investigator do?
```

Stores:

```
doc_id

notes_summary

fraud_likelihood

primary_next_doc

alt_doc_leads

open_questions
```

---

Cognee is knowledge memory.

The buffer is investigation history.

Both are required.

---

# Evidence Model Integration

Cognee discoveries are never treated as evidence.

They are investigation leads.

Example:

Cognee discovers:

```
Vendor A connected to Employee B
```

The final finding must reference:

```
Evidence:

Document:
Berechtigungsauswertung.xlsx

Page:
3

Passage:
MV-U05 has vendor creation and payment approval rights.
```

Rule:

```
Relationships generate hypotheses.

Documents prove conclusions.
```

---

# Data Pipeline

New ingestion flow:

```
User Uploads Documents

↓

Document Parser

↓

Text Extraction

↓

Cognee Ingestion

↓

Entity Extraction

↓

Relationship Graph Creation

↓

Vector Memory Creation

↓

Investigation Agent
```

---

# Backend Changes

New backend modules:

```
backend/

├── cognee/
│
│   ├── client.py
│   ├── ingestion.py
│   ├── retrieval.py
│   ├── graph.py
│   └── schemas.py
│
├── investigation_agent/
│
├── evidence/
│
├── buffer/
│
└── tavily_mcp/
```

---

# Cognee Client Wrapper

The application should not call Cognee directly everywhere.

Create an internal wrapper:

```
CogneeClient
```

Responsibilities:

- initialize Cognee
- ingest documents
- query knowledge
- retrieve relationships
- return structured responses

Example:

```python
class CogneeClient:

    async def ingest_documents(files):
        pass


    async def search_context(query):
        pass


    async def find_related_entities(entity):
        pass


    async def get_relationship_graph(entity):
        pass
```

---

# Investigation Tools

The Investigation Agent can access:

## Internal Tools

- document retrieval
- evidence lookup
- Cognee knowledge search
- entity relationship search
- fraud classifier

## External Tools

- Tavily MCP

Used for:

- company history
- regulations
- accounting standards
- similar fraud cases
- public records

---

# Frontend Improvements

Add an investigation graph visualization.

Example:

```
Vendor

 |

Invoices

 |

Payments

 |

Employee

 |

Permissions
```

The auditor should be able to understand:

- why a document was analyzed
- what relationships were discovered
- what evidence supports the conclusion

---

# API Changes

## POST /investigations/{id}/memory/build

Creates the Cognee knowledge layer.

Response:

```json
{
    "status": "building"
}
```

---

## GET /investigations/{id}/graph

Returns:

```json
{
    "entities": [],
    "relationships": []
}
```

Used for visualization.

---

## GET /investigations/{id}/related

Returns related:

- documents
- entities
- transactions
- employees
- vendors

---

# Configuration

Environment variables:

```env
COGNEE_ENABLED=true

COGNEE_STORAGE_PATH=/tmp/cognee

COGNEE_MODEL=gpt-5-mini
```

---

# Evaluation

The Cognee integration is successful if:

- hidden relationships are discovered
- fewer irrelevant documents are analyzed
- investigation paths become shorter
- fraud schemes are detected faster
- investigators can visualize relationships
- evidence traceability remains unchanged

---

# Expected Benefits

## Better Fraud Detection

Especially for:

- fake vendors
- collusion
- duplicate payments
- approval manipulation
- related-party transactions
- financial statement manipulation

---

## Better Explainability

Auditors can answer:

```
Why did the AI investigate this document?
```

because the relationship path is visible.

---

## Better Scalability

The system can extend from:

```
20 documents
```

to:

```
hundreds or thousands of documents
```

without relying only on prompt context.

---

# Final Architecture

```
                    Documents

                        |

                        v

              Document Processing

                        |

                        v

                    Cognee

        --------------------------------

        Entity Graph

        Vector Memory

        Relationship Discovery

        --------------------------------


                        |

                        v

            Investigation Agent

                        |

                        v

              DFS Investigation

                        |

                        v

            Investigation Buffer

                        |

                        v

              Evidence Report

                        |

                        v

                 Human Auditor
```

---

# MVP Principle

Cognee does not replace the investigator.

Cognee gives the investigator memory.

The LLM performs the investigation.

Evidence proves the conclusion.