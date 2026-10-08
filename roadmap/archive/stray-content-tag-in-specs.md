+++
id = "stray-content-tag-in-specs"
title = "The stray `</content>` tag in the main specs is gone"
filed = 2026-08-31
closed = 2026-08-31
outcome = "shipped"
+++

**The stray `</content>` tag in the main specs is gone** (2026-08-31),
resolving the repo-hygiene item **Now** carried as open question 6, with no
change proposal: two lines, no spec text touched, 41/41 specs still
validating. By the time anyone
looked it was two files and not the three the item recorded —
`stream-iterate/spec.md` and `collector-to-map/spec.md`.
`collector-to-set/spec.md` had lost its copy without anyone noticing, because
`mark-order-blind-collectors` rewrote that file's tail for its own reasons.

**That is the finding worth keeping: the tag was never fixed, it was
*overwritten*.** A defect that disappears only when something else happens to
rewrite the same lines is one nothing was watching, which is why this one was
rediscoverable three times. `openspec validate --specs` passes with the tag
and passes without it — the parser ignores trailing junk — so no gate here
would ever have caught it.
