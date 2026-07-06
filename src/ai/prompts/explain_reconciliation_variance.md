---
version: 1.0
model: stub (product: claude via bedrock, pinned)
temperature: 0.1
output_contract: src/ai/contracts.py
---
# Explain a reconciliation variance

Contract: finding + sample records -> {explanation, likely_cause, suggested_check, confidence}. Must reference the actual delta values; no invented numbers (checked programmatically).
