# Delegated-limit shortcut — 0.19.2

Pending management approvals now show **Change delegated limits** on inbox cards, business leadership requests, generic approval forms and successful approval preview dialogs. The link identifies the affected business and opens its manager authority form directly in Management overview. Relevant director and existing authority-contract sections also expand. A stale search cannot hide the destination.

The stock-order/routine-purchase limit is editable through the existing validated authority form. Director shared daily limits, contract commitments and parent restrictions remain in force. Following the link is read-only. Updating limits does not itself approve the pending request; a return-to-inbox link supports the separate review step. No save migration or simulation change is required. Unknown or unowned request IDs do not produce links, and unrelated preview dialogs clear any previous shortcut.

Validation: 55 targeted tests passed across delegated shortcuts, blocker navigation, inbox, management and authority; three focused tests passed again after tightening the scroll anchor. Two existing dependency deprecation warnings remain. Browser checks on a disposable campaign copy verified the card link, approval popup link, correct business, expanded authority controls and current zero-dollar purchase limit. Installation excludes campaign saves and verifies source hashes and ten installed page views.

Next: retain these contextual shortcuts when adding other approval types. A failed approval preview continues to use the existing error recovery shortcuts.
