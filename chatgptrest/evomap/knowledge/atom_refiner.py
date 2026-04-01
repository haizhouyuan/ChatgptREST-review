"""AtomRefiner — LLM-powered post-processor for heuristic knowledge atoms.

Takes atoms extracted by heuristic methods (heading-based splitting) and
refines them using LLM calls for:
  1. Question generation — turn heading text into proper questions
  2. Canonical question normalization — for dedup
  3. Atom type classification — beyond keyword heuristics
  4. Quality scoring — assess answer quality, groundedness, reusability
  5. Constraint extraction — scope, context, preconditions

Designed to run in batch mode (all atoms for a document/episode) or
on-demand for individual atoms.

Usage::

    refiner = AtomRefiner(db=db, llm_fn=my_llm_call)
    result = refiner.refine_batch(episode_id="ep_xxx")
    # result = RefineResult(refined=12, skipped=3, errors=0)

    # Or refine all unrefined atoms:
    result = refiner.refine_all(limit=100)

The LLM function signature::

    def llm_fn(prompt: str, system: str) -> str:
        '''Send prompt to LLM and return text response.'''
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, AtomType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class RefinerConfig:
    """Configuration for atom refinement."""
    # LLM constraints
    batch_size: int = 10          # atoms per LLM call (reduces cost)
    max_prompt_chars: int = 6000  # truncate long answers
    
    # Quality thresholds
    min_answer_chars: int = 30    # skip very short atoms
    min_question_chars: int = 5   # questions must be meaningful
    
    # Scoring
    score_quality: bool = True    # ask LLM to score atoms
    
    # Skip already-refined atoms
    skip_refined: bool = True     # skip atoms with status >= SCORED
    
    # Language
    language: str = "auto"        # auto-detect or force zh/en


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class RefineResult:
    """Result of a refinement run."""
    refined: int = 0
    skipped: int = 0
    errors: int = 0
    elapsed_ms: int = 0


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a knowledge engineer specializing in atomic knowledge extraction \
from AI-agent conversation artifacts. The domain is AI coding agent \
development (ChatgptREST, browser automation, LLM orchestration, DevOps). \
Content is bilingual (Chinese + English) — preserve the original language \
of questions and answers.

For each atom, you must produce:
1. A proper natural-language QUESTION that the answer addresses.
   - MUST be a complete, standalone question — not a section heading.
   - If the heading is in Chinese, the question SHOULD be in Chinese.
   - If the heading is in English or code-related, use English.
2. A canonical_question (normalized, lowercase, no punctuation, English preferred) for dedup.
3. The correct atom_type from: qa, decision, procedure, troubleshooting, lesson.
   - decision: records a design choice and its rationale.
   - procedure: step-by-step instructions or operational runbook.
   - troubleshooting: diagnosis of a problem and its fix.
   - lesson: hard-won insight or post-mortem takeaway.
   - qa: general knowledge that doesn't fit the above.
4. Quality scores (0.0-1.0):
   - quality_auto: overall answer quality (completeness, accuracy, clarity).
   - novelty: how novel/unique is this knowledge (0.1 for obvious, 0.9 for rare insight).
   - groundedness: how well-grounded in evidence/code (0.9 if references specific code/config).
   - reusability: how reusable across contexts (0.9 if broadly applicable).
   - confidence: your confidence in the classification.
5. constraints: JSON array of applicability constraints (e.g., ["ChatgptREST only", "Python 3.11+"]).

Return ONLY valid JSON, no markdown fences, no explanation."""

_BATCH_TEMPLATE = """\
Refine these {count} knowledge atoms. Each has a raw "heading" (used as question) \
and an "answer" (the section content). Generate proper questions and metadata.

{atoms_json}

Return a JSON array of objects, one per atom, in the same order:
[
  {{
    "atom_id": "original_id",
    "question": "A proper question the answer addresses",
    "canonical_question": "normalized lowercase question for dedup",
    "atom_type": "qa|decision|procedure|troubleshooting|lesson",
    "quality_auto": 0.0-1.0,
    "novelty": 0.0-1.0,
    "groundedness": 0.0-1.0,
    "reusability": 0.0-1.0,
    "confidence": 0.0-1.0,
    "constraints": "JSON array of applicability constraints (optional)"
  }}
]"""


# ---------------------------------------------------------------------------
# AtomRefiner
# ---------------------------------------------------------------------------

class AtomRefiner:
    """LLM-powered post-processor for heuristic knowledge atoms."""

    def __init__(
        self,
        db: KnowledgeDB,
        llm_fn: Callable[[str, str], str] | None = None,
        config: RefinerConfig | None = None,
    ):
        self.db = db
        self._llm_fn = llm_fn
        self._config = config or RefinerConfig()

    # ── Public API ────────────────────────────────────────────────

    def refine_all(self, limit: int = 500) -> RefineResult:
        """Refine all unrefined atoms (status=CANDIDATE, no canonical_question)."""
        start = time.time()
        conn = self.db.connect()
        
        # Find atoms that need refinement
        rows = conn.execute(
            """SELECT * FROM atoms 
               WHERE (canonical_question = '' OR canonical_question IS NULL)
                 AND LENGTH(answer) >= ?
               ORDER BY valid_from DESC
               LIMIT ?""",
            (self._config.min_answer_chars, limit),
        ).fetchall()
        
        atoms = [Atom.from_row(dict(r)) for r in rows]
        logger.info("AtomRefiner: found %d atoms to refine", len(atoms))
        
        result = RefineResult()
        total_batches = (len(atoms) + self._config.batch_size - 1) // self._config.batch_size
        
        # Process in batches with progress logging
        for batch_idx, i in enumerate(range(0, len(atoms), self._config.batch_size)):
            batch = atoms[i:i + self._config.batch_size]
            batch_start = time.time()
            batch_result = self._refine_batch(batch)
            batch_elapsed = time.time() - batch_start
            
            result.refined += batch_result.refined
            result.skipped += batch_result.skipped
            result.errors += batch_result.errors
            
            remaining = total_batches - (batch_idx + 1)
            eta_s = remaining * batch_elapsed if remaining > 0 else 0
            logger.info(
                "Batch %d/%d: +%d refined, +%d err (%.1fs) | "
                "cumulative: refined=%d err=%d | ETA: %.0fs",
                batch_idx + 1, total_batches,
                batch_result.refined, batch_result.errors, batch_elapsed,
                result.refined, result.errors, eta_s,
            )
        
        result.elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            "AtomRefiner: refined=%d, skipped=%d, errors=%d in %dms",
            result.refined, result.skipped, result.errors, result.elapsed_ms,
        )
        return result

    def refine_episode(self, episode_id: str) -> RefineResult:
        """Refine all atoms in a specific episode."""
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT * FROM atoms WHERE episode_id = ?",
            (episode_id,),
        ).fetchall()
        atoms = [Atom.from_row(dict(r)) for r in rows]
        return self._refine_batch(atoms)

    # ── Private ───────────────────────────────────────────────────

    def _refine_batch(self, atoms: list[Atom]) -> RefineResult:
        """Refine a batch of atoms using a single LLM call."""
        result = RefineResult()
        
        if not atoms:
            return result
            
        if not self._llm_fn:
            # No LLM available — apply heuristic refinement only
            for atom in atoms:
                self._heuristic_refine(atom)
                self._save_atom(atom)
                result.refined += 1
            return result
        
        # Prepare batch input
        atoms_data = []
        for atom in atoms:
            answer_text = atom.answer[:self._config.max_prompt_chars]
            if len(answer_text) < self._config.min_answer_chars:
                result.skipped += 1
                continue
            atoms_data.append({
                "atom_id": atom.atom_id,
                "heading": atom.question,  # current heading-as-question
                "answer": answer_text,
                "current_type": atom.atom_type,
            })
        
        if not atoms_data:
            return result
        
        prompt = _BATCH_TEMPLATE.format(
            count=len(atoms_data),
            atoms_json=json.dumps(atoms_data, ensure_ascii=False, indent=2),
        )
        
        try:
            raw = self._llm_fn(prompt, _SYSTEM_PROMPT)
            refinements = self._parse_refinements(raw)
            
            # Apply refinements
            atom_by_id = {a.atom_id: a for a in atoms}
            for ref in refinements:
                atom_id = ref.get("atom_id", "")
                atom = atom_by_id.get(atom_id)
                if not atom:
                    continue
                
                self._apply_refinement(atom, ref)
                self._save_atom(atom)
                result.refined += 1
            
            # Count unmatched atoms as errors
            result.errors = len(atoms_data) - result.refined
            
        except Exception as e:
            logger.warning("LLM refinement failed, falling back to heuristic: %s", e)
            for atom in atoms:
                self._heuristic_refine(atom)
                self._save_atom(atom)
                result.refined += 1
        
        return result

    def _parse_refinements(self, raw: str) -> list[dict]:
        """Parse LLM response into refinement dicts."""
        # Try to find JSON array
        raw = raw.strip()
        
        # Remove markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:])
            if raw.rstrip().endswith("```"):
                raw = raw.rstrip()[:-3]
        
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            return [data]
        except json.JSONDecodeError:
            # Try to extract JSON from mixed content
            match = re.search(r'\[[\s\S]*\]', raw)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning("Could not parse LLM refinement response")
            return []

    def _apply_refinement(self, atom: Atom, ref: dict) -> None:
        """Apply LLM refinement to an atom."""
        if q := ref.get("question"):
            atom.question = q
        if cq := ref.get("canonical_question"):
            atom.canonical_question = cq
        if at := ref.get("atom_type"):
            # Validate atom type
            valid_types = {t.value for t in AtomType}
            if at in valid_types:
                atom.atom_type = at
        
        # Scores
        for field_name in ("quality_auto", "novelty", "groundedness", "reusability", "confidence"):
            val = ref.get(field_name)
            if val is not None:
                try:
                    setattr(atom, field_name, float(val))
                except (ValueError, TypeError):
                    pass
        
        # Constraints
        if constraints := ref.get("constraints"):
            if isinstance(constraints, str):
                atom.constraints = constraints
            else:
                atom.constraints = json.dumps(constraints, ensure_ascii=False)
        
        # Mark as scored
        atom.status = AtomStatus.SCORED.value

    def _heuristic_refine(self, atom: Atom) -> None:
        """Apply heuristic refinement when no LLM is available."""
        heading = atom.question.strip()
        
        # Generate a basic question from heading
        if heading and not heading.endswith("?") and not heading.endswith("？"):
            # Strip leading numbers "1." "2." etc.
            clean = re.sub(r'^[\d]+[.、)\]】]\s*', '', heading)
            # Strip emoji
            clean = re.sub(r'[🔴🟡🟢🔥💡⚡🎯⚠️✅❌📌🏗️🛡️🔍🔧]+', '', clean).strip()
            
            if clean:
                # Generate question form
                atom.question = f"What is the approach for: {clean}?"
                atom.canonical_question = clean.lower().strip("?？。.!！")
        
        # Basic quality heuristic
        answer_len = len(atom.answer)
        if answer_len > 500:
            atom.quality_auto = 0.6
        elif answer_len > 200:
            atom.quality_auto = 0.5
        else:
            atom.quality_auto = 0.3
        
        atom.status = AtomStatus.SCORED.value

    def _save_atom(self, atom: Atom) -> None:
        """Update atom in database."""
        conn = self.db.connect()
        row = atom.to_row()
        
        # Build UPDATE for non-pk fields
        fields = [k for k in row if k != "atom_id"]
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = [row[k] for k in fields]
        values.append(row["atom_id"])
        
        conn.execute(
            f"UPDATE atoms SET {set_clause} WHERE atom_id=?",
            values,
        )
        conn.commit()
