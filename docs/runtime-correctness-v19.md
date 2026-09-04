# Runtime Correctness — Phase 19

## Canonical user-uploaded indexing surface

The maintained application now has one implementation of `UserUploadedFileIndexer`: `user_uploaded_file_indexer_upgraded.py`.

The historical module path remains available as a compatibility re-export, so callers do not need to change imports while the duplicate implementation is retired.

### Boundary

`Application → backend.user_uploaded_file_indexer → indexer.user_uploaded_file_indexer → upgraded implementation`

### Why this matters

The previous layout maintained two implementations of the same upload-indexing contract. That creates drift risk: fixes to persistence, path safety, reindexing, or query behavior could land in one implementation but not the other.

Phase 19 removes that ambiguity from the maintained import surface without changing the public class name.

### Validation

Top-level regression coverage verifies that the compatibility modules re-export rather than define another `UserUploadedFileIndexer` class. No local test suite was executed; CI remains authoritative.
