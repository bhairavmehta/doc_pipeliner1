Order tracking service requirements (#123456)

Parent: #123400, "Order tracking." State is Active.
Ask: Define what the service needs:
Inputs: carrier feeds and a shared list of order statuses.
Outputs: a status history for every order and customer notifications.
Also define: how carrier data is handled, how reprocessing behaves, and how new statuses are handed off for review.
Agreement: get the team to agree which carriers are in scope for the first release.
Evidence: A requirements document covering all of the above. It should draw on the research findings.
Comments from the team:
Jan 8: please include a diagram of the flow.
Jan 12, an open question: should we poll carriers on a schedule or use webhooks?
