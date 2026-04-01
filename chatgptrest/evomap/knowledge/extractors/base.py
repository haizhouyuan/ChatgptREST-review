"""Base class for EvoMap knowledge extractors."""

from __future__ import annotations

import logging
from typing import Iterator

from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, Evidence

logger = logging.getLogger(__name__)

class BaseExtractor:
    """Abstract base class for all EvoMap knowledge extractors."""

    source_name: str = "base"

    def __init__(self, db):
        self.db = db

    def extract_all(self) -> None:
        """Run the full extraction pipeline: Docs -> Episodes -> Atoms -> Evidence."""
        for doc in self.extract_documents():
            self.db.put_document(doc)
            
            for episode in self.extract_episodes(doc):
                self.db.put_episode(episode)
                
                for atom in self.extract_atoms(episode):
                    self.db.put_atom(atom)
                    
                    for evidence in self.extract_evidence(atom, episode):
                        self.db.put_evidence(evidence)
        
        self.db.commit()

    def extract_documents(self) -> Iterator[Document]:
        """Yield documents to process."""
        yield from []

    def extract_episodes(self, doc: Document) -> Iterator[Episode]:
        """Extract episodes from a document."""
        yield from []

    def extract_atoms(self, episode: Episode) -> Iterator[Atom]:
        """Extract atoms from an episode."""
        yield from []

    def extract_evidence(self, atom: Atom, episode: Episode) -> Iterator[Evidence]:
        """Extract evidence linking an atom back to its source episode/document."""
        yield from []
