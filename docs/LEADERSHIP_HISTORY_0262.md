# Leadership career tracking — 0.26.2

Director and executive appointments now create dated entries in the employee's Career and employment history. Entries identify the leadership role, businesses, appointed spending limit, actual employer and monthly base pay. Added/removed scope, changed limits, executive role changes and director removal record the before/after duties. Replacing a director records the change on both employees and names the replacement in the outgoing employee's history. An unchanged repeat appointment adds no career entry.

The employee page now shows Current leadership duties immediately above career history, with business links and access to management policies. This reads existing assignments, so current directors in older saves are visible immediately. Earlier appointment dates are not fabricated or backfilled. Base positions, reporting lines, employee identity, payroll ownership, authority checks and promotion-pay rules remain unchanged.

History uses the existing persisted person history and its existing 50-entry retention limit. The current-duties panel is derived independently from saved leadership assignments. This increment does not create an unlimited lifetime archive or retrospectively reconstruct past appointments. Broader history retention is a possible follow-up.

Validation: 88 distinct targeted tests passed across leadership history (5 new), leadership pay, leadership, leadership activity, completion systems and employee management. The five history tests were also rerun after final UI wording changes. Tests cover dated entries, scope and limit changes, removal, replacement across employers, executives, repeat suppression, rejected actions without mutation, read-only old-save display and previews, HTTP rendering, save/load consistency and financial audit. The full repository suite and browser visual QA were not run. Two existing dependency deprecation warnings remain.

Installation backs up changed source files and checks their hashes. Saved games are not modified during installation. Restart the game to load version 0.26.2.
