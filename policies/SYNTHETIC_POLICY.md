# Synthetic Acceptable-Use and Access-Review Policy (v1.0, Group 8B demo)

> FICTIONAL DOCUMENT written for a university class project. It is not the policy of any real
> organization and must not be cited as one. Section IDs (e.g. `SP-3.1`) are used for citations.

## SP-1.1 Purpose and scope
This policy describes how analysts review unusual login and access activity on organization accounts.
Unusual activity is a reason to review, not evidence of misconduct. Reviews must be fair, documented,
and limited to the minimum information needed.

## SP-1.2 Human review requirement
Automated tools may prioritize and summarize activity, but a human analyst must review every finding.
No account may be disabled, privileges revoked, or a person disciplined solely on the basis of an
automated risk score. Enforcement actions require analyst review and manager approval.

## SP-2.1 Working hours and after-hours access
Accounts are expected to sign in during their assigned working hours or shift. After-hours or
off-hours access is permitted when it supports approved work such as on-call duty, a night shift,
or a scheduled change window. Off-hours sign-ins without such context should be reviewed against
shift schedules and change records.

## SP-2.2 Remote access and VPN
Remote access must use the approved VPN. Sign-ins from a new or unfamiliar location label should be
confirmed with the account owner through a trusted channel, because location labels can be affected
by VPN routing, travel, or proxies and do not by themselves identify who used the account.

## SP-2.3 Failed sign-in attempts
Repeated failed sign-in attempts may indicate a forgotten password, a misconfigured device, or
password guessing. A burst of failures followed by a successful login should be reviewed: confirm with
the account owner whether they made the attempts, and check for password reset requests.

## SP-3.1 Privileged access review
Privileged actions (administrator rights, permission changes, domain controller or backup system
administration) must be performed only by accounts assigned privileged roles. Privileged access
outside assigned work hours should be reviewed against an authorized change record. A privileged
action by an account with no privileged role should be escalated for analyst review.

## SP-3.2 Change records
Planned administrative work must have an approved change record listing the account, date, time
window and systems. When activity matches an approved change record, the analyst should note the
change ID and confirm the activity stayed within the approved window and systems.

## SP-3.3 Access to unfamiliar systems
Access to a system that an account has not used before is common when job duties change. Analysts
should confirm whether the account has a business need for the system (for example a new project
or role change) before drawing conclusions.

## SP-4.1 Privacy and data minimization
Investigations must use only the activity records needed to answer the review question. Analysts
must not label a person as malicious or guilty based on log data alone, since logs show account
activity, not who was physically present.

## SP-4.2 Recording the outcome
Each review should record the finding, evidence event IDs, questions asked, the answer received,
and the outcome: reviewed and closed, needs more context, or escalated.
