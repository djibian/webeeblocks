----------------------------- MODULE WebeeBlocksV5 -----------------------------
EXTENDS Naturals, FiniteSets, TLC

(*
WebeeBlocks V5-0 — abstract authority protocol.

This model covers authority, governance migration and rollback.
It deliberately does NOT model product-task scheduling.

Normal guarantees hold only while guaranteeActive = TRUE.
HumanGovernanceOverride leaves the guarantee envelope.

Abstract actions requiring separate GitHub refinement evidence:
- append one Authority Ledger event,
- create/update one Protocol Gate Check Run,
- create/dismiss one REQUEST_CHANGES review,
- a recoverable exact-head merge transaction around GitHub expected_head_sha,
- one human-rooted governance configuration step.
*)

CONSTANTS
  Epochs, Heads, PRs, Proposals, Rejections, Findings,
  Owner, ExternalActor,
  ProposalActor, ProposalKind, ProposalHead, ProposalFinding, ProposalEpoch,
  RejectionProposal, RejectionEpoch, RejectionHead, RejectionPR,
  RejectionFindings,
  Applies,
  LegacyFindings, LegacyRejectedHeads,
  CheckpointHeads,
  InitialPRs, InitialPRHead, InitialEpoch,
  FaultInjection

ProposalKinds ==
  {"GO", "NO_GO", "UNPROVEN_BLOCKING", "UNPROVEN_NONBLOCKING",
   "DISPOSITION_RESOLVED", "DISPOSITION_NLA",
   "HUMAN_PASS", "HUMAN_FAIL", "HUMAN_NA"}

NegativeKinds == {"NO_GO", "UNPROVEN_BLOCKING", "HUMAN_FAIL"}
DispositionKinds == {"DISPOSITION_RESOLVED", "DISPOSITION_NLA"}
CheckpointStates == {"NONE", "PENDING", "PASS", "FAIL", "NA"}

ASSUME /\ Epochs # {}
       /\ Heads # {}
       /\ PRs # {}
       /\ Proposals # {}
       /\ Rejections # {}
       /\ Findings # {}
       /\ Owner # ExternalActor
       /\ ProposalActor \in [Proposals -> {Owner, ExternalActor}]
       /\ ProposalKind \in [Proposals -> ProposalKinds]
       /\ ProposalHead \in [Proposals -> Heads]
       /\ ProposalFinding \in [Proposals -> Findings]
       /\ ProposalEpoch \in [Proposals -> Epochs]
       /\ RejectionProposal \in [Rejections -> Proposals]
       /\ RejectionEpoch \in [Rejections -> Epochs]
       /\ RejectionHead \in [Rejections -> Heads]
       /\ RejectionPR \in [Rejections -> PRs]
       /\ RejectionFindings \in [Rejections -> SUBSET Findings]
       /\ \A r \in Rejections :
            /\ RejectionFindings[r] # {}
            /\ ProposalKind[RejectionProposal[r]] \in NegativeKinds
            /\ RejectionEpoch[r] = ProposalEpoch[RejectionProposal[r]]
            /\ RejectionHead[r] = ProposalHead[RejectionProposal[r]]
       /\ \A p \in Proposals :
            ProposalKind[p] \in NegativeKinds =>
              Cardinality({r \in Rejections : RejectionProposal[r] = p}) = 1
       /\ Applies \subseteq (Findings \X Heads)
       /\ LegacyFindings \subseteq Findings
       /\ LegacyRejectedHeads \subseteq Heads
       /\ CheckpointHeads \subseteq Heads
       /\ InitialPRs \subseteq PRs
       /\ InitialPRHead \in [PRs -> Heads]
       /\ InitialEpoch \in Epochs
       /\ FaultInjection \in BOOLEAN

AnyHead == CHOOSE h \in Heads : TRUE

VARIABLES
  guaranteeActive,

  prOpen,
  prHead,
  baseFresh,
  merged,
  mergeHead,
  trunkBlocked,

  mergePrepared,
  mergeSubmitted,
  mergeRemoteSucceeded,
  mergeRemoteFailed,
  mergeCancelled,
  mergeCommitted,
  mergeIntentHead,
  mergeIntentEpoch,

  proposalPresent,
  proposalCorrupt,

  prepared,
  linearized,
  committed,
  authorityFindingHistory,
  dispositions,
  importedLegacy,
  importedLegacyRejectedHeads,

  checkpoint,

  gateSuccess,
  gateFailure,
  gateFresh,
  gateCount,
  poisonPrepared,
  poisoned,
  poisonCommitted,

  activeReviews,
  corruptedReviews,

  manifestObservable,
  manifestMatches,
  bootstrapped,
  requiredEpochs,
  operationalEpochs,
  retiredEpochs,
  activeEpoch,

  v4Guard,
  v4Verified,
  v5Retired,
  v4ProjectedFindings,
  v4ProjectedRejectedHeads,
  v4ProjectedCheckpoints,
  v4ProjectedTrunkBlocked,

  positiveAudit

vars ==
  << guaranteeActive,
     prOpen, prHead, baseFresh, merged, mergeHead, trunkBlocked,
     mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed,
     mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch,
     proposalPresent, proposalCorrupt,
     prepared, linearized, committed, authorityFindingHistory, dispositions, importedLegacy,
     importedLegacyRejectedHeads,
     checkpoint,
     gateSuccess, gateFailure, gateFresh, gateCount, poisonPrepared, poisoned, poisonCommitted,
     activeReviews, corruptedReviews,
     manifestObservable, manifestMatches, bootstrapped,
     requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
     v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads,
     v4ProjectedCheckpoints, v4ProjectedTrunkBlocked,
     positiveAudit >>

Pairs == Epochs \X Heads

TypeOK ==
  /\ guaranteeActive \in BOOLEAN
  /\ prOpen \subseteq PRs
  /\ prHead \in [PRs -> Heads]
  /\ baseFresh \in [PRs -> BOOLEAN]
  /\ merged \subseteq PRs
  /\ mergeHead \in [PRs -> Heads]
  /\ trunkBlocked \in BOOLEAN
  /\ mergePrepared \subseteq PRs
  /\ mergeSubmitted \subseteq mergePrepared
  /\ mergeRemoteSucceeded \subseteq mergeSubmitted
  /\ mergeRemoteFailed \subseteq mergeSubmitted
  /\ mergeRemoteSucceeded \cap mergeRemoteFailed = {}
  /\ mergeCancelled \subseteq (mergePrepared \ mergeSubmitted)
  /\ mergeCommitted \subseteq
       (mergeRemoteSucceeded \cup mergeRemoteFailed \cup mergeCancelled)
  /\ mergeIntentHead \in [PRs -> Heads]
  /\ mergeIntentEpoch \in [PRs -> Epochs]

  /\ proposalPresent \subseteq Proposals
  /\ proposalCorrupt \subseteq Proposals

  /\ prepared \subseteq Rejections
  /\ linearized \subseteq Rejections
  /\ committed \subseteq Rejections
  /\ authorityFindingHistory \subseteq Findings
  /\ dispositions \subseteq (Findings \X Heads)
  /\ importedLegacy \subseteq LegacyFindings
  /\ importedLegacyRejectedHeads \subseteq LegacyRejectedHeads

  /\ checkpoint \in [Pairs -> CheckpointStates]

  /\ gateSuccess \subseteq Pairs
  /\ gateFailure \subseteq Pairs
  /\ gateFresh \subseteq Pairs
  /\ gateCount \in [Pairs -> Nat]
  /\ poisonPrepared \subseteq Pairs
  /\ poisoned \subseteq Pairs
  /\ poisonCommitted \subseteq Pairs

  /\ activeReviews \subseteq (PRs \X Rejections)
  /\ corruptedReviews \subseteq (PRs \X Rejections)

  /\ manifestObservable \in [Epochs -> BOOLEAN]
  /\ manifestMatches \in [Epochs -> BOOLEAN]
  /\ bootstrapped \subseteq Epochs
  /\ requiredEpochs \subseteq Epochs
  /\ operationalEpochs \subseteq Epochs
  /\ retiredEpochs \subseteq Epochs
  /\ activeEpoch \in Epochs

  /\ v4Guard \in BOOLEAN
  /\ v4Verified \in BOOLEAN
  /\ v5Retired \in BOOLEAN
  /\ v4ProjectedFindings \subseteq Findings
  /\ v4ProjectedRejectedHeads \subseteq Heads
  /\ v4ProjectedCheckpoints \subseteq Heads
  /\ v4ProjectedTrunkBlocked \in BOOLEAN

  /\ positiveAudit \subseteq Pairs

Trusted(p) ==
  /\ p \in proposalPresent
  /\ p \notin proposalCorrupt
  /\ ProposalActor[p] = Owner

TrustedNegative(p) ==
  /\ p \in proposalPresent
  /\ ProposalActor[p] = Owner
  /\ ProposalKind[p] \in NegativeKinds

TrustedGo(p) ==
  /\ Trusted(p)
  /\ ProposalKind[p] = "GO"

TrustedGoFor(p,e) ==
  /\ TrustedGo(p)
  /\ ProposalEpoch[p] = e

TrustedDisposition(p) ==
  /\ Trusted(p)
  /\ ProposalKind[p] \in DispositionKinds

PreparedNegativeProposals ==
  {RejectionProposal[r] : r \in prepared}

UnpreparedTrustedNegatives(h) ==
  {p \in Proposals :
    /\ TrustedNegative(p)
    /\ ProposalHead[p] = h
    /\ p \notin PreparedNegativeProposals}

UnpreparedTrustedNegativeProposals ==
  {p \in Proposals :
    /\ TrustedNegative(p)
    /\ p \notin PreparedNegativeProposals}

UnpreparedTrustedNegativesForEpoch(e) ==
  {p \in UnpreparedTrustedNegativeProposals : ProposalEpoch[p] = e}

AuthorityFindings ==
  UNION {RejectionFindings[r] : r \in linearized}

PendingRejections ==
  prepared \ linearized

PendingFindings ==
  UNION {RejectionFindings[r] : r \in PendingRejections}

PendingRejectionsForHead(h) ==
  {r \in PendingRejections : RejectionHead[r] = h}

UncommittedRejections ==
  linearized \ committed

PendingForEpoch(e) ==
  {r \in PendingRejections : RejectionEpoch[r] = e}

UncommittedForEpoch(e) ==
  {r \in UncommittedRejections : RejectionEpoch[r] = e}

PendingPoisonForEpoch(e) ==
  {x \in poisonPrepared \ poisoned : x[1] = e}

UncommittedPoisonForEpoch(e) ==
  {x \in poisoned \ poisonCommitted : x[1] = e}

DuplicatePairs ==
  {x \in Pairs : gateCount[x] > 1}

UnpreparedPoisonForEpoch(e) ==
  {x \in DuplicatePairs \ poisonPrepared : x[1] = e}

KnownDuplicatePairs ==
  DuplicatePairs \cup poisonPrepared

UnreconciledDuplicatePairs ==
  KnownDuplicatePairs \ poisonCommitted

UnreconciledDuplicateHeads ==
  {h \in Heads : \E e \in Epochs : <<e,h>> \in UnreconciledDuplicatePairs}

OutstandingMerges ==
  mergePrepared \ mergeCommitted

MergeTransactionIdle ==
  OutstandingMerges = {}

MergeOutcomeKnown(pr) ==
  pr \in (mergeRemoteSucceeded \cup mergeRemoteFailed)

EpochAuthorityQuiescent(e) ==
  /\ MergeTransactionIdle
  /\ UnpreparedTrustedNegativesForEpoch(e) = {}
  /\ PendingForEpoch(e) = {}
  /\ UncommittedForEpoch(e) = {}
  /\ UnpreparedPoisonForEpoch(e) = {}
  /\ PendingPoisonForEpoch(e) = {}
  /\ UncommittedPoisonForEpoch(e) = {}

DurableFindings ==
  importedLegacy \cup AuthorityFindings

UnresolvedDurable(h) ==
  {f \in DurableFindings :
     /\ <<f,h>> \in Applies
     /\ <<f,h>> \notin dispositions}

UnresolvedPending(h) ==
  {f \in PendingFindings :
     /\ <<f,h>> \in Applies
     /\ <<f,h>> \notin dispositions}

V5FindingsForDowngrade ==
  AuthorityFindings

V5RejectedHeads ==
  {h \in Heads : \E r \in linearized : RejectionHead[r] = h}

V5PoisonedHeads ==
  {h \in Heads : \E e \in Epochs : <<e,h>> \in poisoned}

V5TerminalHeads ==
  V5RejectedHeads \cup V5PoisonedHeads

MergedHeads ==
  {mergeHead[pr] : pr \in merged}

TrustedAuthorityProposals ==
  {p \in proposalPresent : ProposalActor[p] = Owner}

TrustedAuthorityProposalHeads ==
  {ProposalHead[p] : p \in TrustedAuthorityProposals}

PositiveAuditHeads ==
  {h \in Heads : \E e \in Epochs : <<e,h>> \in positiveAudit}

AuthoritySeenHeads ==
  TrustedAuthorityProposalHeads \cup PositiveAuditHeads \cup
  MergedHeads \cup V5TerminalHeads

HeadTerminal(h) ==
  h \in (importedLegacyRejectedHeads \cup V5TerminalHeads)

FindingOriginHeads(f) ==
  {h \in Heads :
    \E r \in linearized :
      /\ f \in RejectionFindings[r]
      /\ RejectionHead[r] = h}

CheckpointAllows(e,h) ==
  IF h \in CheckpointHeads
  THEN checkpoint[<<e,h>>] \in {"PASS", "NA"}
  ELSE TRUE

RequiredCheckpointsOK(h) ==
  \A e \in requiredEpochs : CheckpointAllows(e,h)

LiveCheckpointHeads ==
  {h \in CheckpointHeads :
    \E e \in requiredEpochs :
      checkpoint[<<e,h>>] \in {"PENDING", "FAIL"}}

NativeBlocked(pr) ==
  \E other \in prOpen, r \in Rejections :
    /\ pr \in prOpen
    /\ <<other,r>> \in activeReviews
    /\ prHead[other] = prHead[pr]

CorruptedForHead(h) ==
  \E pr \in prOpen, r \in Rejections :
    /\ <<pr,r>> \in corruptedReviews
    /\ prHead[pr] = h

TerminalFailure(e,h) ==
  HeadTerminal(h)

UniqueFreshSuccess(e,h) ==
  /\ <<e,h>> \in gateSuccess
  /\ <<e,h>> \notin gateFailure
  /\ <<e,h>> \in gateFresh
  /\ gateCount[<<e,h>>] = 1

RequiredGatesOK(h) ==
  \A e \in requiredEpochs :
    /\ manifestObservable[e]
    /\ manifestMatches[e]
    /\ UniqueFreshSuccess(e,h)

V4KnownFindings ==
  LegacyFindings \cup v4ProjectedFindings

V4RejectedHeads ==
  LegacyRejectedHeads \cup v4ProjectedRejectedHeads

V4Unresolved(h) ==
  {f \in V4KnownFindings :
     /\ <<f,h>> \in Applies
     /\ <<f,h>> \notin dispositions}

V4Allows(pr) ==
  /\ ~v4ProjectedTrunkBlocked
  /\ prHead[pr] \notin V4RejectedHeads
  /\ V4Unresolved(prHead[pr]) = {}
  /\ prHead[pr] \notin v4ProjectedCheckpoints

V5Allows(pr) ==
  /\ ~trunkBlocked
  /\ ~HeadTerminal(prHead[pr])
  /\ RequiredGatesOK(prHead[pr])
  /\ UnresolvedDurable(prHead[pr]) = {}
  /\ RequiredCheckpointsOK(prHead[pr])
  /\ ~CorruptedForHead(prHead[pr])

MergeAllowed(pr) ==
  /\ guaranteeActive
  /\ pr \in prOpen
  /\ baseFresh[pr]
  /\ (v4Guard => V4Allows(pr))
  /\ (requiredEpochs # {} => V5Allows(pr))
  /\ ~NativeBlocked(pr)

NoGuardGap ==
  \/ ~guaranteeActive
  \/ v4Guard
  \/ requiredEpochs # {}

LegacyImportComplete ==
  /\ importedLegacy = LegacyFindings
  /\ importedLegacyRejectedHeads = LegacyRejectedHeads

DowngradeProjectionComplete ==
  /\ V5FindingsForDowngrade \subseteq v4ProjectedFindings
  /\ V5TerminalHeads \subseteq v4ProjectedRejectedHeads
  /\ LiveCheckpointHeads \subseteq v4ProjectedCheckpoints
  /\ (trunkBlocked => v4ProjectedTrunkBlocked)

Init ==
  /\ guaranteeActive = TRUE

  /\ prOpen = InitialPRs
  /\ prHead = InitialPRHead
  /\ baseFresh = [p \in PRs |-> TRUE]
  /\ merged = {}
  /\ mergeHead = [p \in PRs |-> AnyHead]
  /\ trunkBlocked = FALSE
  /\ mergePrepared = {}
  /\ mergeSubmitted = {}
  /\ mergeRemoteSucceeded = {}
  /\ mergeRemoteFailed = {}
  /\ mergeCancelled = {}
  /\ mergeCommitted = {}
  /\ mergeIntentHead = [p \in PRs |-> AnyHead]
  /\ mergeIntentEpoch = [p \in PRs |-> InitialEpoch]

  /\ proposalPresent = {}
  /\ proposalCorrupt = {}

  /\ prepared = {}
  /\ linearized = {}
  /\ committed = {}
  /\ authorityFindingHistory = {}
  /\ dispositions = {}
  /\ importedLegacy = {}
  /\ importedLegacyRejectedHeads = {}

  /\ checkpoint =
       [x \in Pairs |->
         IF x[2] \in CheckpointHeads THEN "PENDING" ELSE "NONE"]

  /\ gateSuccess = {}
  /\ gateFailure = {}
  /\ gateFresh = {}
  /\ gateCount = [x \in Pairs |-> 0]
  /\ poisonPrepared = {}
  /\ poisoned = {}
  /\ poisonCommitted = {}

  /\ activeReviews = {}
  /\ corruptedReviews = {}

  /\ manifestObservable = [e \in Epochs |-> FALSE]
  /\ manifestMatches = [e \in Epochs |-> FALSE]
  /\ bootstrapped = {}
  /\ requiredEpochs = {}
  /\ operationalEpochs = {}
  /\ retiredEpochs = {}
  /\ activeEpoch = InitialEpoch

  /\ v4Guard = TRUE
  /\ v4Verified = TRUE
  /\ v5Retired = FALSE
  /\ v4ProjectedFindings = {}
  /\ v4ProjectedRejectedHeads = {}
  /\ v4ProjectedCheckpoints = {}
  /\ v4ProjectedTrunkBlocked = FALSE

  /\ positiveAudit = {}

PublishProposal(p) ==
  /\ ~v5Retired
  /\ p \in Proposals \ proposalPresent
  /\ ProposalEpoch[p] = activeEpoch
  /\ proposalPresent' = proposalPresent \cup {p}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

EditProposal(p) ==
  /\ p \in proposalPresent \ proposalCorrupt
  /\ proposalCorrupt' = proposalCorrupt \cup {p}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

ApplyCheckpointResult(p) ==
  LET e == ProposalEpoch[p]
      h == ProposalHead[p]
      x == <<e,h>>
  IN  /\ Trusted(p)
      /\ e = activeEpoch
      /\ e \in requiredEpochs
      /\ manifestObservable[e]
      /\ manifestMatches[e]
      /\ h \in CheckpointHeads
      /\ ProposalKind[p] \in {"HUMAN_PASS","HUMAN_NA"}
      /\ checkpoint[x] = "PENDING"
      /\ checkpoint' =
           [checkpoint EXCEPT
             ![x] =
               CASE ProposalKind[p] = "HUMAN_PASS" -> "PASS"
                 [] OTHER -> "NA"]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

PrepareRejection(r) ==
  LET p == RejectionProposal[r]
  IN  /\ r \in Rejections \ prepared
      /\ requiredEpochs # {}
      /\ TrustedNegative(p)
      /\ p \notin PreparedNegativeProposals
      /\ ProposalHead[p] = RejectionHead[r]
      /\ RejectionEpoch[r] = ProposalEpoch[p]
      /\ prepared' = prepared \cup {r}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint,
                      gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                      positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

LinearizeNegative(r) ==
  LET e == RejectionEpoch[r]
      h == RejectionHead[r]
      x == <<e,h>>
  IN  /\ r \in prepared \ linearized
      /\ (gateCount[x] <= 1 \/ x \in poisoned)
      /\ gateFailure' = gateFailure \cup {x}
      /\ gateSuccess' = gateSuccess \ {x}
      /\ gateFresh' = gateFresh \ {x}
      /\ gateCount' = [gateCount EXCEPT ![x] = IF @ = 0 THEN 1 ELSE @]
      /\ checkpoint' =
           IF ProposalKind[RejectionProposal[r]] = "HUMAN_FAIL"
           THEN [checkpoint EXCEPT ![x] = "FAIL"]
           ELSE checkpoint
      /\ linearized' = linearized \cup {r}
      /\ authorityFindingHistory' =
           authorityFindingHistory \cup RejectionFindings[r]
      /\ trunkBlocked' =
           IF h \in MergedHeads THEN TRUE ELSE trunkBlocked
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                      positiveAudit, poisonPrepared, poisonCommitted, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

CommitRejection(r) ==
  /\ r \in linearized \ committed
  /\ committed' = committed \cup {r}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

CreateReviewProjection(r) ==
  /\ ~v5Retired
  /\ requiredEpochs # {}
  /\ r \in committed
  /\ RejectionPR[r] \in prOpen
  /\ <<RejectionPR[r],r>> \notin activeReviews
  /\ \E f \in RejectionFindings[r] :
       /\ <<f,prHead[RejectionPR[r]]>> \in Applies
       /\ <<f,prHead[RejectionPR[r]]>> \notin dispositions
  /\ activeReviews' = activeReviews \cup {<<RejectionPR[r],r>>}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

CorruptReview(pr,r) ==
  /\ <<pr,r>> \in activeReviews
  /\ corruptedReviews' = corruptedReviews \cup {<<pr,r>>}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

AddDisposition(p) ==
  LET f == ProposalFinding[p]
      h == ProposalHead[p]
  IN  /\ TrustedDisposition(p)
      /\ ProposalEpoch[p] = activeEpoch
      /\ activeEpoch \in requiredEpochs
      /\ f \in DurableFindings
      /\ h \notin FindingOriginHeads(f)
      /\ <<f,h>> \notin dispositions
      /\ dispositions' = dispositions \cup {<<f,h>>}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint,
                      gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                      positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

ProjectionResolved(pr,r) ==
  /\ pr \in prOpen
  /\ \A f \in RejectionFindings[r] :
       \/ <<f,prHead[pr]>> \notin Applies
       \/ <<f,prHead[pr]>> \in dispositions

DismissProjection(pr,r) ==
  /\ ~v5Retired
  /\ <<pr,r>> \in activeReviews
  /\ ProjectionResolved(pr,r)
  /\ activeReviews' = activeReviews \ {<<pr,r>>}
  /\ corruptedReviews' = corruptedReviews \ {<<pr,r>>}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

PositiveEligible(e,h) ==
  /\ e = activeEpoch
  /\ e \in requiredEpochs
  /\ e \in bootstrapped
  /\ LegacyImportComplete
  /\ manifestObservable[e]
  /\ manifestMatches[e]
  /\ ~TerminalFailure(e,h)
  /\ h \notin UnreconciledDuplicateHeads
  /\ UnpreparedTrustedNegatives(h) = {}
  /\ PendingRejectionsForHead(h) = {}
  /\ UnresolvedDurable(h) = {}
  /\ UnresolvedPending(h) = {}
  /\ CheckpointAllows(e,h)
  /\ ~CorruptedForHead(h)
  /\ \A pr \in prOpen : prHead[pr] = h => ~NativeBlocked(pr)

PublishSuccess(p,e,h) ==
  LET x == <<e,h>>
  IN  /\ TrustedGoFor(p,e)
      /\ ProposalHead[p] = h
      /\ PositiveEligible(e,h)
      /\ gateCount[x] = 0
      /\ gateSuccess' = gateSuccess \cup {x}
      /\ gateFresh' = gateFresh \cup {x}
      /\ gateCount' = [gateCount EXCEPT ![x] = 1]
      /\ positiveAudit' = positiveAudit \cup {x}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint,
                      gateFailure, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

ExpireSuccess(e,h) ==
  LET x == <<e,h>>
  IN  /\ x \in gateSuccess
      /\ x \in gateFresh
      /\ gateFresh' = gateFresh \ {x}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint,
                      gateSuccess, gateFailure, gateCount, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                      positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

RevalidateSuccess(p,e,h) ==
  LET x == <<e,h>>
  IN  /\ TrustedGoFor(p,e)
      /\ ProposalHead[p] = h
      /\ PositiveEligible(e,h)
      /\ x \in gateSuccess
      /\ x \notin gateFresh
      /\ gateCount[x] = 1
      /\ gateFresh' = gateFresh \cup {x}
      /\ positiveAudit' = positiveAudit \cup {x}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint,
                      gateSuccess, gateFailure, gateCount, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

InjectDuplicate(e,h) ==
  LET x == <<e,h>>
  IN  /\ FaultInjection
      /\ ~v5Retired
      /\ e \in requiredEpochs
      /\ gateCount[x] = 1
      /\ gateCount' = [gateCount EXCEPT ![x] = 2]
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint,
                      gateSuccess, gateFailure, gateFresh, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                      positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

PreparePoison(e,h) ==
  LET x == <<e,h>>
  IN  /\ x \in DuplicatePairs
      /\ x \notin poisonPrepared
      /\ poisonPrepared' = poisonPrepared \cup {x}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead, trunkBlocked,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, authorityFindingHistory, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint,
                      gateSuccess, gateFailure, gateFresh, gateCount, poisoned, poisonCommitted,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints, v4ProjectedTrunkBlocked,
                      positiveAudit, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

LinearizePoison(e,h) ==
  LET x == <<e,h>>
  IN  /\ x \in poisonPrepared \ poisoned
      /\ poisoned' = poisoned \cup {x}
      /\ gateFailure' = gateFailure \cup {x}
      /\ gateSuccess' = gateSuccess \ {x}
      /\ gateFresh' = gateFresh \ {x}
      /\ gateCount' = [gateCount EXCEPT ![x] = IF @ = 0 THEN 1 ELSE @]
      /\ trunkBlocked' =
           IF h \in MergedHeads THEN TRUE ELSE trunkBlocked
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, authorityFindingHistory, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint, poisonPrepared, poisonCommitted,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints, v4ProjectedTrunkBlocked,
                      positiveAudit, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

CommitPoison(e,h) ==
  LET x == <<e,h>>
  IN  /\ x \in poisoned \ poisonCommitted
      /\ poisonCommitted' = poisonCommitted \cup {x}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead, trunkBlocked,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, authorityFindingHistory, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint,
                      gateSuccess, gateFailure, gateFresh, gateCount, poisonPrepared, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints, v4ProjectedTrunkBlocked,
                      positiveAudit, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

LoseCheckProjection(e,h) ==
  LET x == <<e,h>>
  IN  /\ FaultInjection
      /\ ~v5Retired
      /\ x \in poisonPrepared \ poisoned
      /\ gateCount[x] > 0
      /\ gateSuccess' = gateSuccess \ {x}
      /\ gateFailure' = gateFailure \ {x}
      /\ gateFresh' = gateFresh \ {x}
      /\ gateCount' = [gateCount EXCEPT ![x] = 0]
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead, trunkBlocked,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, authorityFindingHistory, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint, poisonPrepared, poisoned, poisonCommitted,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints, v4ProjectedTrunkBlocked,
                      positiveAudit, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

ConfigureEpoch(e) ==
  /\ e \in Epochs \ bootstrapped
  /\ ~manifestObservable[e]
  /\ ~manifestMatches[e]
  /\ manifestObservable' = [manifestObservable EXCEPT ![e] = TRUE]
  /\ manifestMatches' = [manifestMatches EXCEPT ![e] = TRUE]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  bootstrapped, requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

LoseObservability(e) ==
  /\ e \in Epochs
  /\ manifestObservable[e]
  /\ manifestObservable' = [manifestObservable EXCEPT ![e] = FALSE]
  /\ operationalEpochs' = operationalEpochs \ {e}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestMatches, bootstrapped, requiredEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

RestoreObservability(e) ==
  /\ e \in bootstrapped
  /\ ~manifestObservable[e]
  /\ manifestMatches[e]
  /\ manifestObservable' = [manifestObservable EXCEPT ![e] = TRUE]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestMatches, bootstrapped, requiredEpochs,
                  operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

DriftGovernance(e) ==
  /\ e \in bootstrapped
  /\ manifestMatches[e]
  /\ manifestMatches' = [manifestMatches EXCEPT ![e] = FALSE]
  /\ operationalEpochs' = operationalEpochs \ {e}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, bootstrapped, requiredEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

BootstrapEpoch(e) ==
  /\ e \in Epochs \ bootstrapped
  /\ manifestObservable[e]
  /\ manifestMatches[e]
  /\ bootstrapped' = bootstrapped \cup {e}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

RequireEpoch(e) ==
  /\ ~v5Retired
  /\ e \notin retiredEpochs
  /\ e \in bootstrapped \ requiredEpochs
  /\ requiredEpochs' = requiredEpochs \cup {e}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

VerifyEpoch(e) ==
  /\ e \in requiredEpochs
  /\ manifestObservable[e]
  /\ manifestMatches[e]
  /\ e \notin operationalEpochs
  /\ operationalEpochs' = operationalEpochs \cup {e}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

AdvanceEpoch(e) ==
  /\ e \in requiredEpochs \cap operationalEpochs
  /\ manifestObservable[e]
  /\ manifestMatches[e]
  /\ e # activeEpoch
  /\ e \notin retiredEpochs
  /\ EpochAuthorityQuiescent(activeEpoch)
  /\ retiredEpochs' = retiredEpochs \cup {activeEpoch}
  /\ activeEpoch' = e
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

RemoveOldEpoch(old) ==
  /\ old \in requiredEpochs
  /\ old # activeEpoch
  /\ EpochAuthorityQuiescent(old)
  /\ \E e \in requiredEpochs \ {old} : e \in operationalEpochs
  /\ requiredEpochs' = requiredEpochs \ {old}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

AuthorityUpgradeProjection ==
  /\ ~LegacyImportComplete
  /\ importedLegacy' = LegacyFindings
  /\ importedLegacyRejectedHeads' = LegacyRejectedHeads
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

RemoveV4Guard ==
  /\ MergeTransactionIdle
  /\ v4Guard
  /\ LegacyImportComplete
  /\ requiredEpochs # {}
  /\ \A e \in requiredEpochs :
       /\ e \in operationalEpochs
       /\ manifestObservable[e]
       /\ manifestMatches[e]
  /\ v4Guard' = FALSE
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Verified, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  v5Retired, positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

RestoreV4Guard ==
  /\ ~v4Guard
  /\ v4Guard' = TRUE
  /\ v4Verified' = FALSE
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  v5Retired, positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

VerifyV4 ==
  /\ v4Guard
  /\ ~v4Verified
  /\ v4Verified' = TRUE
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  v5Retired, positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

AuthorityDowngradeProjection ==
  /\ v4Guard
  /\ v4Verified
  /\ ~DowngradeProjectionComplete
  /\ v4ProjectedFindings' = v4ProjectedFindings \cup V5FindingsForDowngrade
  /\ v4ProjectedRejectedHeads' =
       v4ProjectedRejectedHeads \cup V5TerminalHeads
  /\ v4ProjectedCheckpoints' =
       v4ProjectedCheckpoints \cup LiveCheckpointHeads
  /\ v4ProjectedTrunkBlocked' =
       IF trunkBlocked THEN TRUE ELSE v4ProjectedTrunkBlocked
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified,
                  v5Retired, positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

RemoveV5Requirements ==
  /\ MergeTransactionIdle
  /\ requiredEpochs # {}
  /\ v4Guard
  /\ v4Verified
  /\ UnpreparedTrustedNegativeProposals = {}
  /\ PendingRejections = {}
  /\ UncommittedRejections = {}
  /\ UnreconciledDuplicatePairs = {}
  /\ poisonPrepared \ poisoned = {}
  /\ poisoned \ poisonCommitted = {}
  /\ activeReviews = {}
  /\ corruptedReviews = {}
  /\ DowngradeProjectionComplete
  /\ requiredEpochs' = {}
  /\ v5Retired' = TRUE
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

ClosePR(pr) ==
  /\ pr \in prOpen
  /\ pr \notin OutstandingMerges
  /\ prOpen' = prOpen \ {pr}
  /\ UNCHANGED << guaranteeActive,
                  prHead, baseFresh, merged, mergeHead, trunkBlocked,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

RetireClosedProjection(pr,r) ==
  /\ pr \notin prOpen
  /\ r \in committed
  /\ \/ <<pr,r>> \in activeReviews
     \/ <<pr,r>> \in corruptedReviews
  /\ activeReviews' = activeReviews \ {<<pr,r>>}
  /\ corruptedReviews' = corruptedReviews \ {<<pr,r>>}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead, trunkBlocked,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

HeadChange(pr,h) ==
  /\ pr \in prOpen
  /\ h \in Heads
  /\ h # prHead[pr]
  /\ h \notin AuthoritySeenHeads
  /\ prHead' = [prHead EXCEPT ![pr] = h]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

BaseAdvance ==
  /\ \E pr \in prOpen : baseFresh[pr]
  /\ baseFresh' =
       [pr \in PRs |-> IF pr \in prOpen THEN FALSE ELSE baseFresh[pr]]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

RefreshBase(pr,h) ==
  /\ pr \in prOpen
  /\ ~baseFresh[pr]
  /\ h \in Heads
  /\ h # prHead[pr]
  /\ h \notin AuthoritySeenHeads
  /\ prHead' = [prHead EXCEPT ![pr] = h]
  /\ baseFresh' = [baseFresh EXCEPT ![pr] = TRUE]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

MergeEffect(pr) ==
  /\ MergeAllowed(pr)
  /\ LET h == prHead[pr]
         remaining == prOpen \ {pr}
     IN  /\ merged' = merged \cup {pr}
         /\ mergeHead' = [mergeHead EXCEPT ![pr] = h]
         /\ prOpen' = remaining
         /\ baseFresh' =
              [q \in PRs |-> IF q \in remaining THEN FALSE ELSE baseFresh[q]]
  /\ UNCHANGED << guaranteeActive,
                  prHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

PreparePublisherMerge(pr) ==
  /\ ~v5Retired
  /\ requiredEpochs # {}
  /\ MergeTransactionIdle
  /\ MergeAllowed(pr)
  /\ mergePrepared' = mergePrepared \cup {pr}
  /\ mergeIntentHead' = [mergeIntentHead EXCEPT ![pr] = prHead[pr]]
  /\ mergeIntentEpoch' = [mergeIntentEpoch EXCEPT ![pr] = activeEpoch]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead, trunkBlocked,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, v4ProjectedTrunkBlocked, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted >>

MergeIntentStillEligible(pr) ==
  /\ pr \in prOpen
  /\ prHead[pr] = mergeIntentHead[pr]
  /\ activeEpoch = mergeIntentEpoch[pr]
  /\ MergeAllowed(pr)

SubmitPublisherMerge(pr) ==
  /\ pr \in mergePrepared \ mergeSubmitted
  /\ pr \notin mergeCancelled
  /\ MergeIntentStillEligible(pr)
  /\ mergeSubmitted' = mergeSubmitted \cup {pr}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead, trunkBlocked,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, v4ProjectedTrunkBlocked, mergePrepared, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

CancelPreparedMerge(pr) ==
  /\ pr \in mergePrepared \ mergeSubmitted
  /\ pr \notin mergeCommitted
  /\ ~MergeIntentStillEligible(pr)
  /\ mergeCancelled' = mergeCancelled \cup {pr}
  /\ mergeCommitted' = mergeCommitted \cup {pr}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead, trunkBlocked,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeIntentHead, mergeIntentEpoch >>

RemoteMergeSuccess(pr) ==
  /\ pr \in mergeSubmitted
  /\ ~MergeOutcomeKnown(pr)
  /\ pr \in prOpen
  /\ prHead[pr] = mergeIntentHead[pr]
  /\ baseFresh[pr]
  /\ LET h == mergeIntentHead[pr]
         remaining == prOpen \ {pr}
     IN  /\ merged' = merged \cup {pr}
         /\ mergeHead' = [mergeHead EXCEPT ![pr] = h]
         /\ prOpen' = remaining
         /\ baseFresh' =
              [q \in PRs |-> IF q \in remaining THEN FALSE ELSE baseFresh[q]]
  /\ mergeRemoteSucceeded' = mergeRemoteSucceeded \cup {pr}
  /\ UNCHANGED << guaranteeActive,
                  prHead, trunkBlocked,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

RemoteMergeFailure(pr) ==
  /\ pr \in mergeSubmitted
  /\ ~MergeOutcomeKnown(pr)
  /\ mergeRemoteFailed' = mergeRemoteFailed \cup {pr}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead, trunkBlocked,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

CommitPublisherMerge(pr) ==
  /\ pr \in mergePrepared \ mergeCommitted
  /\ MergeOutcomeKnown(pr)
  /\ mergeCommitted' = mergeCommitted \cup {pr}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead, trunkBlocked,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeIntentHead, mergeIntentEpoch >>


V4MergePR(pr) ==
  /\ MergeTransactionIdle
  /\ requiredEpochs = {}
  /\ v4Guard
  /\ MergeEffect(pr)

HumanGovernanceOverride ==
  /\ guaranteeActive
  /\ guaranteeActive' = FALSE
  /\ UNCHANGED << prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy, importedLegacyRejectedHeads,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints,
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked, mergePrepared, mergeSubmitted, mergeRemoteSucceeded, mergeRemoteFailed, mergeCancelled, mergeCommitted, mergeIntentHead, mergeIntentEpoch >>

PublisherNormalStep ==
  \/ \E p \in Proposals : ApplyCheckpointResult(p)
  \/ \E r \in Rejections : PrepareRejection(r)
  \/ \E r \in Rejections : LinearizeNegative(r)
  \/ \E r \in Rejections : CommitRejection(r)
  \/ \E r \in Rejections : CreateReviewProjection(r)
  \/ \E p \in Proposals : AddDisposition(p)
  \/ \E pr \in PRs, r \in Rejections : DismissProjection(pr,r)
  \/ \E pr \in PRs, r \in Rejections : RetireClosedProjection(pr,r)
  \/ \E p \in Proposals, e \in Epochs, h \in Heads : PublishSuccess(p,e,h)
  \/ \E p \in Proposals, e \in Epochs, h \in Heads : RevalidateSuccess(p,e,h)
  \/ \E e \in Epochs, h \in Heads : PreparePoison(e,h)
  \/ \E e \in Epochs, h \in Heads : LinearizePoison(e,h)
  \/ \E e \in Epochs, h \in Heads : CommitPoison(e,h)
  \/ \E pr \in PRs : PreparePublisherMerge(pr)
  \/ AuthorityUpgradeProjection
  \/ AuthorityDowngradeProjection

MergeReconciliationStep ==
  \/ \E pr \in PRs : SubmitPublisherMerge(pr)
  \/ \E pr \in PRs : CancelPreparedMerge(pr)
  \/ \E pr \in PRs : CommitPublisherMerge(pr)

PublisherStep ==
  /\ ~v5Retired
  /\ IF MergeTransactionIdle
        THEN PublisherNormalStep
        ELSE MergeReconciliationStep

EnvironmentStep ==
  \/ \E p \in Proposals : PublishProposal(p)
  \/ \E pr \in PRs : RemoteMergeSuccess(pr)
  \/ \E pr \in PRs : RemoteMergeFailure(pr)
  \/ \E pr \in PRs : ClosePR(pr)
  \/ \E p \in Proposals : EditProposal(p)
  \/ \E pr \in PRs, r \in Rejections : CorruptReview(pr,r)
  \/ \E e \in Epochs, h \in Heads : ExpireSuccess(e,h)
  \/ \E e \in Epochs, h \in Heads : InjectDuplicate(e,h)
  \/ \E e \in Epochs, h \in Heads : LoseCheckProjection(e,h)
  \/ \E e \in Epochs : ConfigureEpoch(e)
  \/ \E e \in Epochs : LoseObservability(e)
  \/ \E e \in Epochs : RestoreObservability(e)
  \/ \E e \in Epochs : DriftGovernance(e)
  \/ \E e \in Epochs : BootstrapEpoch(e)
  \/ \E e \in Epochs : RequireEpoch(e)
  \/ \E e \in Epochs : VerifyEpoch(e)
  \/ \E e \in Epochs : AdvanceEpoch(e)
  \/ \E e \in Epochs : RemoveOldEpoch(e)
  \/ RemoveV4Guard
  \/ RestoreV4Guard
  \/ VerifyV4
  \/ RemoveV5Requirements
  \/ \E pr \in PRs, h \in Heads : HeadChange(pr,h)
  \/ BaseAdvance
  \/ \E pr \in PRs, h \in Heads : RefreshBase(pr,h)
  \/ \E pr \in PRs : V4MergePR(pr)
  \/ HumanGovernanceOverride

Next ==
  \/ PublisherStep
  \/ EnvironmentStep

SafetySpec ==
  /\ Init
  /\ [][Next]_vars

Spec ==
  /\ SafetySpec
  /\ WF_vars(PublisherStep)

(***************************************************************************)
(* INVARIANTS TO MODEL-CHECK                                               *)
(***************************************************************************)

Inv_NoGuardGap ==
  NoGuardGap

Inv_LinearizedWasPrepared ==
  linearized \subseteq prepared

Inv_CommittedWasLinearized ==
  committed \subseteq linearized

Inv_PoisonLinearizedWasPrepared ==
  poisoned \subseteq poisonPrepared

Inv_PoisonCommittedWasLinearized ==
  poisonCommitted \subseteq poisoned

Inv_NoPositiveAfterTerminalFailure ==
  \A e \in Epochs, h \in Heads :
    HeadTerminal(h) => ~UniqueFreshSuccess(e,h)

Inv_MergeNeverUsesTerminalHead ==
  \A pr \in PRs :
    /\ MergeAllowed(pr)
    /\ requiredEpochs # {}
    => ~HeadTerminal(prHead[pr])

Inv_MergeHasNoUnresolvedDurableFinding ==
  \A pr \in PRs :
    /\ MergeAllowed(pr)
    /\ requiredEpochs # {}
    => UnresolvedDurable(prHead[pr]) = {}

Inv_MergeRequiresCheckpoint ==
  \A pr \in PRs :
    /\ MergeAllowed(pr)
    /\ requiredEpochs # {}
    => RequiredCheckpointsOK(prHead[pr])

Inv_V4ProjectedCheckpointBlocksMerge ==
  \A pr \in PRs :
    prHead[pr] \in v4ProjectedCheckpoints => ~MergeAllowed(pr)

Inv_MergeHasNoCorruptedProjection ==
  \A pr \in PRs :
    /\ MergeAllowed(pr)
    /\ requiredEpochs # {}
    => ~CorruptedForHead(prHead[pr])

Inv_MergeRequiresObservableManifest ==
  \A pr \in PRs :
    /\ MergeAllowed(pr)
    /\ requiredEpochs # {}
    => \A e \in requiredEpochs :
         /\ manifestObservable[e]
         /\ manifestMatches[e]

Inv_V4RemovalRequiresImportedAuthority ==
  ~v4Guard =>
    /\ LegacyImportComplete
    /\ requiredEpochs # {}

Inv_V5RemovalRequiresV4Fallback ==
  /\ guaranteeActive
  /\ requiredEpochs = {}
  => v4Guard

Inv_V4ProjectionPreservesTerminalHeads ==
  /\ guaranteeActive
  /\ v5Retired
  => V5TerminalHeads \subseteq v4ProjectedRejectedHeads

Inv_NoPendingAfterV5Removal ==
  /\ guaranteeActive
  /\ requiredEpochs = {}
  => PendingRejections = {}

Inv_EpochChangeDoesNotEraseFindings ==
  AuthorityFindings = authorityFindingHistory

Inv_OperationalEpochsAreCurrentlyHealthy ==
  \A e \in operationalEpochs :
    /\ manifestObservable[e]
    /\ manifestMatches[e]

Inv_PendingRejectionBlocksPositiveEligibility ==
  \A e \in Epochs, h \in Heads :
    PendingRejectionsForHead(h) # {} => ~PositiveEligible(e,h)

Inv_ObservedTrustedNegativeBlocksPositiveEligibility ==
  \A p \in proposalPresent :
    /\ ProposalActor[p] = Owner
    /\ ProposalKind[p] \in NegativeKinds
    => ~PositiveEligible(ProposalEpoch[p], ProposalHead[p])

Inv_UnreconciledDuplicateBlocksPositiveEligibility ==
  \A e \in Epochs, h \in Heads :
    h \in UnreconciledDuplicateHeads => ~PositiveEligible(e,h)

Inv_LateRefutationBlocksV5Merge ==
  trunkBlocked =>
    \A pr \in PRs :
      requiredEpochs # {} => ~MergeAllowed(pr)

Inv_V4ProjectedTrunkBlockBlocksMerge ==
  v4ProjectedTrunkBlocked =>
    \A pr \in PRs : ~MergeAllowed(pr)

Inv_NoTwoMergedPRsShareExactHead ==
  \A p1 \in merged, p2 \in merged :
    p1 # p2 => mergeHead[p1] # mergeHead[p2]

Inv_SingleOutstandingMerge ==
  Cardinality(OutstandingMerges) <= 1

Inv_SubmittedMergeWasPrepared ==
  mergeSubmitted \subseteq mergePrepared

Inv_RemoteMergeOutcomeWasSubmitted ==
  (mergeRemoteSucceeded \cup mergeRemoteFailed) \subseteq mergeSubmitted

Inv_MergeCommitHasResolution ==
  mergeCommitted \subseteq
    (mergeRemoteSucceeded \cup mergeRemoteFailed \cup mergeCancelled)

Inv_NoV5RetirementWithOutstandingMerge ==
  v5Retired => OutstandingMerges = {}

Inv_ActiveEpochNeverRetired ==
  activeEpoch \notin retiredEpochs

Inv_V5RetiredClosesPublisher ==
  v5Retired => ~ENABLED PublisherStep

Inv_V5RetiredClosesProposalPublication ==
  v5Retired =>
    \A p \in Proposals : ~ENABLED PublishProposal(p)

(***************************************************************************)
(* REVIEW / REFINEMENT OBLIGATIONS                                         *)
(***************************************************************************)

(*
R1 Authority Ledger:
prepared, committed, poisonPrepared, poisoned, poisonCommitted, dispositions,
importedLegacy and V4 projections refine append-only Git history. Protocol App may append; it must not have a bypass
allowing deletion or non-fast-forward history rewrite.

R2 Negative crash consistency:
PREPARE is durable before LinearizeNegative. A crash after Gate FAILURE but
before COMMIT must be reconstructible from PREPARE. Once a trusted negative
proposal is protocol-visible, later mutation of its mutable GitHub projection
does not withdraw it; explicit authoritative resolution is required. Such
observed negative authority blocks new SUCCESS even before PREPARE. Once PREPARED, the rejection
blocks its exact RejectionHead independently of semantic Applies; finding
applicability governs inheritance to other candidate heads, not the head-level
NO_GO barrier. PREPARE does not retroactively erase an already fresh SUCCESS:
until Gate FAILURE linearizes the negative, a merge race is classified as late
refutation by the deliberate boundary in REVIEW.md.

R3 Gate:
UniqueFreshSuccess abstracts exactly one fresh Check Run from the exact
Protocol App. Same-name checks from any other App do not count.

R3a Review projection:
CreateReviewProjection is enabled only while at least one rejection finding is
still applicable and unresolved for that PR's current head. Once a resolved
projection is dismissed it cannot oscillate back into existence unless a later
head makes the rejection semantically blocking again.

R4 Duplicate:
an undetected second Protocol-App writer is outside the normal trust envelope.
InjectDuplicate exists to falsify recovery logic. Duplicate recovery is a
durable PREPARE -> Gate FAILURE -> COMMIT poison lifecycle. A detected duplicate
blocks positive authority for its Head across epochs until poison COMMIT.
After PREPARE, Gate FAILURE may be conservatively reasserted even if Check
retention removed the original duplicate evidence. Physical duplicate Check
Runs may remain forever. A pending NO_GO on an already-poisoned pair can
linearize without requiring a unique Gate.

R5 Epoch:
findings are independent from activeEpoch and requiredEpochs. Governance change
never erases unresolved authority. A Head that has ever been authoritatively
rejected or poisoned is terminal across all epochs: repair requires a distinct
Head. GO proposals and unapplied disposition proposals are epoch-bound and can
mint authority only in the active, required epoch; a disposition already
applied in its epoch remains durable history. Operational epoch membership is
current-health state: observability loss or manifest drift removes the epoch
from operationalEpochs. A temporary loss can be verified again only while the
manifest still matches; observed drift requires a new epoch. Epoch succession
is monotone: when E1 is replaced by E2, E1 enters retiredEpochs and can never
become active or required again in that protocol instance.

R6 Rollback:
RemoveV5Requirements is impossible until V4 is restored and verified, all
trusted negative proposals have been prepared, every rejection PREPARE has
linearized and COMMITted, every duplicate poison PREPARE has linearized and
COMMITted, every physical duplicate is reconciled by durable poison authority,
V5 review projections are cleared, and every authoritative V5 finding, terminal
Head, live checkpoint and trunk-health block has a V4-compatible projection.
Physical duplicate Check Runs need not disappear. Candidate-specific
dispositions never retire findings at global scope, so downgrade conservatively
preserves findings that may become applicable to future candidates.
PrepareRejection and duplicate injection are disabled after V5 retirement.

R7 Merge:
MergePR abstracts expected_head_sha = current prHead[pr] plus strict current
base. A successful merge atomically makes every remaining open PR base-stale.
RefreshBase creates a new Head identity, modeling the real protected-base
update that invalidates exact-candidate positive evidence. Neither RefreshBase
nor ordinary HeadChange may select a Head that has already been integrated;
that would not refine a current-base candidate. A deliberate root-human merge
outside the protocol is a governance override, not a protocol transition.

R7a Late refutation and merge serialization:
while V5 is required, normal merge effects execute only inside PublisherStep.
Controllers may propose integration but do not own the GitHub merge effect.
Gate FAILURE, duplicate poison, positive publication and merge are ordered by
the same serialized Authority Plane. If Gate FAILURE or duplicate poison
linearizes after the exact head has already merged, trunkBlocked becomes TRUE.
Normal later V5 integration stops. Rollback projects that block into V4 before
V5 retirement. Recovery of an
unhealthy trunk is intentionally outside this V5-0 autonomous model and remains
a V4/human-rooted repair obligation.

R8 Liveness:
WF_vars(PublisherStep) abstracts periodic reconciliation. Under a stable finite
environment the publisher is expected to reconstruct after every effect and run
until quiescence. Reviewers should challenge whether this fairness assumption is
implementable.

R9 Human root:
all strong guarantees are conditioned on guaranteeActive = TRUE.
*)

=============================================================================
