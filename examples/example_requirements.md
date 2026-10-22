---
title: Order Tracking Service – Requirements
subtitle: User Story 123456 · Parent #123400: Order tracking (fictional example)
footer: US 123456 · Order Tracking Service Requirements
---

> Fictional example. It shows the structure, depth and style the pipeline should produce. Replace it with one of your own reviewed documents for best results (--example).

<!-- widths: 1.5, 5.0 -->
| Item | Detail |
|---|---|
| **User story** | 123456 – Order tracking service requirements |
| **Parent** | #123400 – Order tracking (Active) |
| **Owner** | to be confirmed |
| **Status** | Draft for team review – decisions needed are marked DECISION |
| **Builds on** | Research findings (Section 11) · supplier data review |
| **Date** | January 15, 2026 |

# 1. Summary

The order tracking service collects shipment events from carriers and shows customers where their order is. It turns each carrier's own status codes into one shared list of statuses, keeps a full history for every order, and sends a notification when the status changes. People in the support team review any new status before it is used.

This document defines the service's inputs, outputs, data handling, reprocessing behavior and review handoff. It also proposes which carriers are in scope for the first release and answers the open question on polling versus webhooks.

## What this story asked for, and where it is covered

<!-- widths: 3.25, 3.25 -->
| Ask | Section |
|---|---|
| Inputs: carrier feeds and the shared status list | 3. Inputs |
| Outputs: order status history and customer notifications | 4. Outputs |
| How carrier data is handled | 5. Data handling |
| How reprocessing behaves | 6. Reprocessing |
| Team agreement on carriers in scope | 8. Carriers in scope (DECISION) |
| Open question: polling or webhooks? | 9. Update method (DECISION) |

# 2. Service at a glance

![Figure 1. Carrier events flow into one status list, a history per order and customer notifications.](fig1_flow.png){width=6.5}

<!-- widths: 2.0, 4.5 -->
| Stage | What it does |
|---|---|
| **1 Collect** | Receive or fetch carrier events and store them unchanged. |
| **2 Map** | Map each carrier status code to one status in the shared list. |
| **3 Update** | Add the event to the order's history and set the current status. |
| **4 Notify** | Send a customer notification when the status changes. |

# 3. Inputs

> Priority: Must = needed for the first release; Should = planned, can follow.

<!-- widths: 0.7, 5.05, 0.75 -->
| ID | Requirement | Priority |
|---|---|---|
| **IN-1** | Carrier feeds. Each carrier is listed in a carrier register with owner, format, update method, rate limits and contact. | Must |
| **IN-2** | Shared status list. A versioned list of statuses (e.g., Shipped, In transit, Delivered, Exception) with a definition for each. | Must |
| **IN-3** | Mapping table from each carrier's codes to the shared list, kept under version control. | Must |
| **IN-4** | Order data: order ID, carrier, tracking number and customer contact preferences. | Must |

# 4. Outputs

<!-- widths: 0.7, 5.05, 0.75 -->
| ID | Requirement | Priority |
|---|---|---|
| **OUT-1** | Status history per order: every event with time, source carrier, original code and mapped status. | Must |
| **OUT-2** | Current status per order, available through an API within 1 minute of a new event. | Must |
| **OUT-3** | Customer notifications on status change, respecting contact preferences. | Must |
| **OUT-4** | Daily report of unmapped codes and late carrier feeds. | Should |

# 5. Data handling

<!-- widths: 0.7, 5.05, 0.75 -->
| ID | Requirement | Priority |
|---|---|---|
| **DH-1** | Raw events are stored unchanged before mapping, so they can be reprocessed. | Must |
| **DH-2** | Duplicate events (same carrier, tracking number, code and time) are stored once. | Must |
| **DH-3** | Unknown carrier codes go to an "Unmapped" status and are flagged for review, never guessed. | Must |
| **DH-4** | Customer contact data is used only for notifications and follows the privacy policy. | Must |

# 6. Reprocessing

<!-- widths: 0.7, 5.05, 0.75 -->
| ID | Requirement | Priority |
|---|---|---|
| **RP-1** | When the mapping table changes, affected orders are reprocessed from the raw events. | Must |
| **RP-2** | Reprocessing never sends a second notification for a status the customer already received. | Must |
| **RP-3** | Each reprocessing run logs what changed: orders, old and new status, mapping version. | Should |

# 7. Review handoff

<!-- widths: 0.7, 5.05, 0.75 -->
| ID | Requirement | Priority |
|---|---|---|
| **RH-1** | New or changed mappings are proposed in a review sheet and approved by the support lead before use. | Must |
| **RH-2** | Each decision records reviewer, date and reason. | Must |

# 8. Carriers in scope (DECISION)

<!-- widths: 1.8, 2.2, 2.5 -->
| Proposal | Carriers | Why |
|---|---|---|
| **In scope (3)** | Carrier A, Carrier B, Carrier C | Together about 85% of orders (research finding 2). |
| **Later (2)** | Carrier D, Carrier E | Low volume; no stable feed yet. |

<!-- widths: 2.5, 1.5, 2.5 -->
| Team member | Agree? (Y / N) | Comments |
|---|---|---|
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |

# 9. Update method (DECISION)

The open question is whether to poll carriers on a schedule or receive webhooks.

<!-- widths: 1.6, 2.45, 2.45 -->
| Option | Pros | Cons |
|---|---|---|
| **A. Polling** | Works with every carrier; simple to control. | Slower updates; uses rate limits. |
| **B. Webhooks** | Near real-time; fewer calls. | Not all carriers offer them; needs a public endpoint. |
| **C. Hybrid – recommended** | Webhooks where offered, polling as fallback; consistent update times. | Two paths to test and monitor. |

> Recommendation: option C. Webhook support for Carrier C is to be confirmed.

# 10. Open items

<!-- widths: 3.3, 1.6, 1.6 -->
| Item | Owner | Needed by |
|---|---|---|
| Agree carriers in scope (Section 8) | Team | Before build |
| Agree update method (Section 9) | Team | Before build |
| Confirm Carrier C webhook support | Integration lead | Before build |

# 11. References

- Research findings for US 123456 (fictional example).
- Carrier integration guides (fictional example).
