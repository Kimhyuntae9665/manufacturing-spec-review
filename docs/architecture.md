# Architecture and trust boundaries
Stdlib loopback HTTP and SQLite; readonly synthetic document sources. API writes only comparisons/human review records, never manufacturing systems.
Part revision differs from document revision. Latest selection is per part/part-revision/role before ACL, with no old-version fallback. Approved references and draft/approved candidates are distinct roles.
SHA256/identity are server-derived. Full raw cells, unique original full-line quotes and server spans must agree. Model metadata is refused. Decimal converts only nominal mm/µm; alternatives/bounds/tolerances require review.
Each model sees one source_text object, never counterpart/gold/filesystem/tools. Localhost inference has a shared persistent timeout barrier.
Comparisons carry source/ACL fingerprints. Source changes invalidate prior reviews. Unauthorized reads cannot mutate unchanged comparisons. Stale views hide previous content/decision/comment; internal history is retained.
Demo profile choices are not enterprise authentication. No production connection or public runtime deployment.
