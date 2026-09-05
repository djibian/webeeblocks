----------------------------- MODULE WebeeBlocksV5 -----------------------------
EXTENDS Naturals, FiniteSets, TLC

(*
WebeeBlocks V5-0 — abstract authority protocol.

This model covers authority, governance migration and rollback.
It deliberately does NOT model product-task scheduling.

Normal guarantees hold only while guaranteeActive = TRUE.
HumanGovernanceOverride leaves the guarantee envelope.

Abstract atomic actions requiring separate GitHub refinement evidence:
- append one Authority Ledger event,
- create/update one Protocol Gate Check Run,
- create/dismiss one REQUEST_CHANGES review,
- exact-head merge using expected_head_sha,
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

  /\ proposalPresent \subseteq Proposals
  /\ proposalCorrupt \subseteq Proposals

  /\ prepared \subseteq Rejections
  /\ linearized \subseteq Rejections
  /\ committed \subseteq Rejections
  /\ authorityFindingHistory \subseteq Findings
  /\ dispositions \subseteq (Findings \X Heads)
  /\ importedLegacy \subseteq LegacyFindings
  /\ importedLegacyRejectedHeads \subseteq LegacyRejectedHeads

  /\ checkpoint \in [Heads -> CheckpointStates]

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
  /\ Trusted(p)
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

EpochAuthorityQuiescent(e) ==
  /\ UnpreparedTrustedNegativesForEpoch(e) = {}
  /\ PendingForEpoch(e) = {}
  /\ UncommittedForEpoch(e) = {}
  /\ PendingPoisonForEpoch(e) = {}
  /\ UncommittedPoisonForEpoch(e) = {}

DuplicatePairs ==
  {x \in Pairs : gateCount[x] > 1}

UnreconciledDuplicatePairs ==
  DuplicatePairs \ poisonCommitted

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

HeadTerminal(h) ==
  h \in (importedLegacyRejectedHeads \cup V5TerminalHeads)

FindingOriginHeads(f) ==
  {h \in Heads :
    \E r \in linearized :
      /\ f \in RejectionFindings[r]
      /\ RejectionHead[r] = h}

CheckpointAllows(h) ==
  IF h \in CheckpointHeads
  THEN checkpoint[h] \in {"PASS", "NA"}
  ELSE TRUE

LiveCheckpointHeads ==
  {h \in CheckpointHeads : checkpoint[h] \in {"PENDING", "FAIL"}}

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
  /\ ~(prHead[pr] \in v4ProjectedCheckpoints /\
       checkpoint[prHead[pr]] \notin {"PASS","NA"})

V5Allows(pr) ==
  /\ ~trunkBlocked
  /\ ~HeadTerminal(prHead[pr])
  /\ RequiredGatesOK(prHead[pr])
  /\ UnresolvedDurable(prHead[pr]) = {}
  /\ CheckpointAllows(prHead[pr])
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
       [h \in Heads |->
         IF h \in CheckpointHeads THEN "PENDING" ELSE "NONE"]

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

ApplyCheckpointResult(p) ==
  /\ Trusted(p)
  /\ ProposalEpoch[p] = activeEpoch
  /\ ProposalHead[p] \in CheckpointHeads
  /\ ProposalKind[p] \in {"HUMAN_PASS","HUMAN_NA"}
  /\ checkpoint[ProposalHead[p]] = "PENDING"
  /\ checkpoint' =
       [checkpoint EXCEPT
         ![ProposalHead[p]] =
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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                      positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
           THEN [checkpoint EXCEPT ![h] = "FAIL"]
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
                      positiveAudit, poisonPrepared, poisonCommitted, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                      positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

PositiveEligible(e,h) ==
  /\ e = activeEpoch
  /\ e \in requiredEpochs
  /\ e \in bootstrapped
  /\ LegacyImportComplete
  /\ manifestObservable[e]
  /\ manifestMatches[e]
  /\ ~TerminalFailure(e,h)
  /\ UnpreparedTrustedNegatives(h) = {}
  /\ PendingRejectionsForHead(h) = {}
  /\ UnresolvedDurable(h) = {}
  /\ UnresolvedPending(h) = {}
  /\ CheckpointAllows(h)
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
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                      positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

InjectDuplicate(e,h) ==
  LET x == <<e,h>>
  IN  /\ FaultInjection
      /\ ~v5Retired
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
                      positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                      positiveAudit >>

LinearizePoison(e,h) ==
  LET x == <<e,h>>
  IN  /\ x \in poisonPrepared \ poisoned
      /\ gateCount[x] > 1
      /\ poisoned' = poisoned \cup {x}
      /\ gateFailure' = gateFailure \cup {x}
      /\ gateSuccess' = gateSuccess \ {x}
      /\ gateFresh' = gateFresh \ {x}
      /\ trunkBlocked' =
           IF h \in MergedHeads THEN TRUE ELSE trunkBlocked
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, authorityFindingHistory, dispositions, importedLegacy, importedLegacyRejectedHeads,
                      checkpoint, gateCount, poisonPrepared, poisonCommitted,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, retiredEpochs, activeEpoch,
                      v4Guard, v4Verified, v5Retired, v4ProjectedFindings, v4ProjectedRejectedHeads, v4ProjectedCheckpoints, v4ProjectedTrunkBlocked,
                      positiveAudit >>

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
                      positiveAudit >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

RemoveV4Guard ==
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
                  v5Retired, positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  v5Retired, positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  v5Retired, positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  v5Retired, positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked >>

RemoveV5Requirements ==
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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

HeadChange(pr,h) ==
  /\ pr \in prOpen
  /\ h \in Heads
  /\ h # prHead[pr]
  /\ h \notin MergedHeads
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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

RefreshBase(pr,h) ==
  /\ pr \in prOpen
  /\ ~baseFresh[pr]
  /\ h \in Heads
  /\ h # prHead[pr]
  /\ h \notin MergedHeads
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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

MergePR(pr) ==
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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

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
                  positiveAudit, authorityFindingHistory, poisonPrepared, poisonCommitted, trunkBlocked, v4ProjectedTrunkBlocked >>

PublisherStep ==
  \/ \E p \in Proposals : ApplyCheckpointResult(p)
  \/ \E r \in Rejections : PrepareRejection(r)
  \/ \E r \in Rejections : LinearizeNegative(r)
  \/ \E r \in Rejections : CommitRejection(r)
  \/ \E r \in Rejections : CreateReviewProjection(r)
  \/ \E p \in Proposals : AddDisposition(p)
  \/ \E pr \in PRs, r \in Rejections : DismissProjection(pr,r)
  \/ \E p \in Proposals, e \in Epochs, h \in Heads : PublishSuccess(p,e,h)
  \/ \E p \in Proposals, e \in Epochs, h \in Heads : RevalidateSuccess(p,e,h)
  \/ \E e \in Epochs, h \in Heads : PreparePoison(e,h)
  \/ \E e \in Epochs, h \in Heads : LinearizePoison(e,h)
  \/ \E e \in Epochs, h \in Heads : CommitPoison(e,h)
  \/ AuthorityUpgradeProjection
  \/ AuthorityDowngradeProjection

EnvironmentStep ==
  \/ \E p \in Proposals : PublishProposal(p)
  \/ \E p \in Proposals : EditProposal(p)
  \/ \E pr \in PRs, r \in Rejections : CorruptReview(pr,r)
  \/ \E e \in Epochs, h \in Heads : ExpireSuccess(e,h)
  \/ \E e \in Epochs, h \in Heads : InjectDuplicate(e,h)
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
  \/ \E pr \in PRs : MergePR(pr)
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
    => CheckpointAllows(prHead[pr])

Inv_V4ProjectedCheckpointBlocksMerge ==
  \A pr \in PRs :
    /\ MergeAllowed(pr)
    /\ prHead[pr] \in v4ProjectedCheckpoints
    => checkpoint[prHead[pr]] \in {"PASS","NA"}

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

Inv_ActiveEpochNeverRetired ==
  activeEpoch \notin retiredEpochs

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
before COMMIT must be reconstructible from PREPARE. A durable trusted negative
proposal blocks new SUCCESS even before PREPARE. Once PREPARED, the rejection
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
durable PREPARE -> Gate FAILURE -> COMMIT poison lifecycle. Physical duplicate
Check Runs may remain forever; governance considers the duplicate reconciled
once poisonCommitted records the append-only poison authority. A pending NO_GO
on an already-poisoned pair can linearize without requiring a unique Gate.

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

R7a Late refutation:
if Gate FAILURE or duplicate poison linearizes after the exact head has already
merged, trunkBlocked becomes TRUE. Normal V5 integration stops immediately.
Rollback projects that block into V4 before V5 retirement. Recovery of an
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
