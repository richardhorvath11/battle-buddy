---
name: catalog
description: Use when reading or resolving the team's service catalog — alert→service resolution, the internal service model, the annotation mapping that populates it, per-field degradation, or catalog freshness. Documents the catalog conventions that stand in for shipped catalog-adapter code.
---

# Catalog

The team's service catalog is the source of truth for what services exist, how
they're owned, and how a firing alert maps onto one of them. This skill
documents the conventions an on-call agent follows when consulting the catalog
— never a parsing library or catalog-adapter code, which this slice
deliberately does not ship (Constitution I; FR-009). The catalog itself lives
in a file-based repository external to this harness; nothing here stores or
duplicates its content.

## Overview
<!-- filled by T017 -->

## Degradation
<!-- filled by T013 -->

## Freshness and runbook references
<!-- filled by T015 -->

## Non-goals
<!-- filled by T017 -->
