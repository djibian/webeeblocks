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
  ProposalActor, ProposalKind, ProposalHead, ProposalFinding,
  RejectionProposal, RejectionEpoch, RejectionHead, RejectionPR,
  RejectionFindings,
  Applies,
  LegacyFindings,
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
       /\ RejectionProposal \in [Rejections -> Proposals]
       /\ RejectionEpoch \in [Rejections -> Epochs]
       /\ RejectionHead \in [Rejections -> Heads]
       /\ RejectionPR \in [Rejections -> PRs]
       /\ RejectionFindings \in [Rejections -> SUBSET Findings]
       /\ \A r \in Rejections : RejectionFindings[r] # {}
       /\ \A p \in Proposals, e \in Epochs :
            ProposalKind[p] \in NegativeKinds =>
              Cardinality({r \in Rejections :
                /\ RejectionProposal[r] = p
                /\ RejectionEpoch[r] = e
                /\ RejectionHead[r] = ProposalHead[p]}) = 1
       /\ Applies \subseteq (Findings \X Heads)
       /\ LegacyFindings \subseteq Findings
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

  proposalPresent,
  proposalCorrupt,

  prepared,
  linearized,
  committed,
  dispositions,
  importedLegacy,

  checkpoint,

  gateSuccess,
  gateFailure,
  gateFresh,
  gateCount,
  poisoned,

  activeReviews,
  corruptedReviews,

  manifestObservable,
  manifestMatches,
  bootstrapped,
  requiredEpochs,
  operationalEpochs,
  activeEpoch,

  v4Guard,
  v4Verified,
  v4ProjectedFindings,
  v4ProjectedCheckpoints,

  positiveAudit

vars ==
  << guaranteeActive,
     prOpen, prHead, baseFresh, merged, mergeHead,
     proposalPresent, proposalCorrupt,
     prepared, linearized, committed, dispositions, importedLegacy,
     checkpoint,
     gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
     activeReviews, corruptedReviews,
     manifestObservable, manifestMatches, bootstrapped,
     requiredEpochs, operationalEpochs, activeEpoch,
     v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
     positiveAudit >>

Pairs == Epochs \X Heads

TypeOK ==
  /\ guaranteeActive \in BOOLEAN
  /\ prOpen \subseteq PRs
  /\ prHead \in [PRs -> Heads]
  /\ baseFresh \in [PRs -> BOOLEAN]
  /\ merged \subseteq PRs
  /\ mergeHead \in [PRs -> Heads]

  /\ proposalPresent \subseteq Proposals
  /\ proposalCorrupt \subseteq Proposals

  /\ prepared \subseteq Rejections
  /\ linearized \subseteq Rejections
  /\ committed \subseteq Rejections
  /\ dispositions \subseteq (Findings \X Heads)
  /\ importedLegacy \subseteq LegacyFindings

  /\ checkpoint \in [Heads -> CheckpointStates]

  /\ gateSuccess \subseteq Pairs
  /\ gateFailure \subseteq Pairs
  /\ gateFresh \subseteq Pairs
  /\ gateCount \in [Pairs -> Nat]
  /\ poisoned \subseteq Pairs

  /\ activeReviews \subseteq (PRs \X Rejections)
  /\ corruptedReviews \subseteq (PRs \X Rejections)

  /\ manifestObservable \in [Epochs -> BOOLEAN]
  /\ manifestMatches \in [Epochs -> BOOLEAN]
  /\ bootstrapped \subseteq Epochs
  /\ requiredEpochs \subseteq Epochs
  /\ operationalEpochs \subseteq Epochs
  /\ activeEpoch \in Epochs

  /\ v4Guard \in BOOLEAN
  /\ v4Verified \in BOOLEAN
  /\ v4ProjectedFindings \subseteq Findings
  /\ v4ProjectedCheckpoints \subseteq Heads

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

AuthorityFindings ==
  UNION {RejectionFindings[r] : r \in linearized}

PendingRejections ==
  prepared \ linearized

PendingFindings ==
  UNION {RejectionFindings[r] : r \in PendingRejections}

DurableFindings ==
  LegacyFindings \cup AuthorityFindings

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

CheckpointAllows(h) ==
  IF h \in CheckpointHeads
  THEN checkpoint[h] \in {"PASS", "NA"}
  ELSE TRUE

LiveCheckpointHeads ==
  {h \in CheckpointHeads : checkpoint[h] \in {"PENDING", "FAIL"}}

NativeBlocked(pr) ==
  \E r \in Rejections :
    /\ <<pr,r>> \in activeReviews
    /\ pr \in prOpen

CorruptedForHead(h) ==
  \E pr \in prOpen, r \in Rejections :
    /\ <<pr,r>> \in corruptedReviews
    /\ prHead[pr] = h

TerminalFailure(e,h) ==
  \/ <<e,h>> \in poisoned
  \/ \E r \in linearized :
       /\ RejectionEpoch[r] = e
       /\ RejectionHead[r] = h

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

V4Unresolved(h) ==
  {f \in V4KnownFindings :
     /\ <<f,h>> \in Applies
     /\ <<f,h>> \notin dispositions}

V4Allows(pr) ==
  /\ V4Unresolved(prHead[pr]) = {}
  /\ ~(prHead[pr] \in v4ProjectedCheckpoints /\
       checkpoint[prHead[pr]] \notin {"PASS","NA"})

V5Allows(pr) ==
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
  importedLegacy = LegacyFindings

DowngradeProjectionComplete ==
  /\ V5FindingsForDowngrade \subseteq v4ProjectedFindings
  /\ LiveCheckpointHeads \subseteq v4ProjectedCheckpoints

Init ==
  /\ guaranteeActive = TRUE

  /\ prOpen = InitialPRs
  /\ prHead = InitialPRHead
  /\ baseFresh = [p \in PRs |-> TRUE]
  /\ merged = {}
  /\ mergeHead = [p \in PRs |-> AnyHead]

  /\ proposalPresent = {}
  /\ proposalCorrupt = {}

  /\ prepared = {}
  /\ linearized = {}
  /\ committed = {}
  /\ dispositions = {}
  /\ importedLegacy = {}

  /\ checkpoint =
       [h \in Heads |->
         IF h \in CheckpointHeads THEN "PENDING" ELSE "NONE"]

  /\ gateSuccess = {}
  /\ gateFailure = {}
  /\ gateFresh = {}
  /\ gateCount = [x \in Pairs |-> 0]
  /\ poisoned = {}

  /\ activeReviews = {}
  /\ corruptedReviews = {}

  /\ manifestObservable = [e \in Epochs |-> FALSE]
  /\ manifestMatches = [e \in Epochs |-> FALSE]
  /\ bootstrapped = {}
  /\ requiredEpochs = {}
  /\ operationalEpochs = {}
  /\ activeEpoch = InitialEpoch

  /\ v4Guard = TRUE
  /\ v4Verified = TRUE
  /\ v4ProjectedFindings = {}
  /\ v4ProjectedCheckpoints = {}

  /\ positiveAudit = {}

PublishProposal(p) ==
  /\ p \in Proposals \ proposalPresent
  /\ proposalPresent' = proposalPresent \cup {p}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

EditProposal(p) ==
  /\ p \in proposalPresent \ proposalCorrupt
  /\ proposalCorrupt' = proposalCorrupt \cup {p}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

ApplyCheckpointResult(p) ==
  /\ Trusted(p)
  /\ ProposalHead[p] \in CheckpointHeads
  /\ ProposalKind[p] \in {"HUMAN_PASS","HUMAN_FAIL","HUMAN_NA"}
  /\ checkpoint[ProposalHead[p]] = "PENDING"
  /\ checkpoint' =
       [checkpoint EXCEPT
         ![ProposalHead[p]] =
           CASE ProposalKind[p] = "HUMAN_PASS" -> "PASS"
             [] ProposalKind[p] = "HUMAN_FAIL" -> "FAIL"
             [] OTHER -> "NA"]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

PrepareRejection(r) ==
  LET p == RejectionProposal[r]
  IN  /\ r \in Rejections \ prepared
      /\ requiredEpochs # {}
      /\ TrustedNegative(p)
      /\ p \notin PreparedNegativeProposals
      /\ ProposalHead[p] = RejectionHead[r]
      /\ RejectionEpoch[r] = activeEpoch
      /\ prepared' = prepared \cup {r}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      linearized, committed, dispositions, importedLegacy,
                      checkpoint,
                      gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, activeEpoch,
                      v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                      positiveAudit >>

LinearizeNegative(r) ==
  LET e == RejectionEpoch[r]
      h == RejectionHead[r]
      x == <<e,h>>
  IN  /\ r \in prepared \ linearized
      /\ gateCount[x] <= 1
      /\ gateFailure' = gateFailure \cup {x}
      /\ gateSuccess' = gateSuccess \ {x}
      /\ gateFresh' = gateFresh \ {x}
      /\ gateCount' = [gateCount EXCEPT ![x] = IF @ = 0 THEN 1 ELSE @]
      /\ linearized' = linearized \cup {r}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, committed, dispositions, importedLegacy,
                      checkpoint,
                      poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, activeEpoch,
                      v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                      positiveAudit >>

CommitRejection(r) ==
  /\ r \in linearized \ committed
  /\ committed' = committed \cup {r}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

CreateReviewProjection(r) ==
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
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

CorruptReview(pr,r) ==
  /\ <<pr,r>> \in activeReviews
  /\ corruptedReviews' = corruptedReviews \cup {<<pr,r>>}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

AddDisposition(p) ==
  LET f == ProposalFinding[p]
      h == ProposalHead[p]
  IN  /\ TrustedDisposition(p)
      /\ f \in DurableFindings
      /\ <<f,h>> \notin dispositions
      /\ dispositions' = dispositions \cup {<<f,h>>}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, importedLegacy,
                      checkpoint,
                      gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, activeEpoch,
                      v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                      positiveAudit >>

ProjectionResolved(pr,r) ==
  /\ pr \in prOpen
  /\ \A f \in RejectionFindings[r] :
       \/ <<f,prHead[pr]>> \notin Applies
       \/ <<f,prHead[pr]>> \in dispositions

DismissProjection(pr,r) ==
  /\ <<pr,r>> \in activeReviews
  /\ ProjectionResolved(pr,r)
  /\ activeReviews' = activeReviews \ {<<pr,r>>}
  /\ corruptedReviews' = corruptedReviews \ {<<pr,r>>}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

PositiveEligible(e,h) ==
  /\ e \in bootstrapped
  /\ manifestObservable[e]
  /\ manifestMatches[e]
  /\ ~TerminalFailure(e,h)
  /\ UnpreparedTrustedNegatives(h) = {}
  /\ UnresolvedDurable(h) = {}
  /\ UnresolvedPending(h) = {}
  /\ CheckpointAllows(h)
  /\ ~CorruptedForHead(h)
  /\ \A pr \in prOpen : prHead[pr] = h => ~NativeBlocked(pr)

PublishSuccess(p,e,h) ==
  LET x == <<e,h>>
  IN  /\ TrustedGo(p)
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
                      prepared, linearized, committed, dispositions, importedLegacy,
                      checkpoint,
                      gateFailure, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, activeEpoch,
                      v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints >>

ExpireSuccess(e,h) ==
  LET x == <<e,h>>
  IN  /\ x \in gateSuccess
      /\ x \in gateFresh
      /\ gateFresh' = gateFresh \ {x}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, dispositions, importedLegacy,
                      checkpoint,
                      gateSuccess, gateFailure, gateCount, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, activeEpoch,
                      v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                      positiveAudit >>

RevalidateSuccess(p,e,h) ==
  LET x == <<e,h>>
  IN  /\ TrustedGo(p)
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
                      prepared, linearized, committed, dispositions, importedLegacy,
                      checkpoint,
                      gateSuccess, gateFailure, gateCount, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, activeEpoch,
                      v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints >>

InjectDuplicate(e,h) ==
  LET x == <<e,h>>
  IN  /\ FaultInjection
      /\ gateCount[x] = 1
      /\ gateCount' = [gateCount EXCEPT ![x] = 2]
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, dispositions, importedLegacy,
                      checkpoint,
                      gateSuccess, gateFailure, gateFresh, poisoned,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, activeEpoch,
                      v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                      positiveAudit >>

PoisonDuplicate(e,h) ==
  LET x == <<e,h>>
  IN  /\ gateCount[x] > 1
      /\ x \notin poisoned
      /\ poisoned' = poisoned \cup {x}
      /\ gateFailure' = gateFailure \cup {x}
      /\ gateSuccess' = gateSuccess \ {x}
      /\ gateFresh' = gateFresh \ {x}
      /\ UNCHANGED << guaranteeActive,
                      prOpen, prHead, baseFresh, merged, mergeHead,
                      proposalPresent, proposalCorrupt,
                      prepared, linearized, committed, dispositions, importedLegacy,
                      checkpoint, gateCount,
                      activeReviews, corruptedReviews,
                      manifestObservable, manifestMatches, bootstrapped,
                      requiredEpochs, operationalEpochs, activeEpoch,
                      v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                      positiveAudit >>

ConfigureEpoch(e) ==
  /\ e \in Epochs
  /\ manifestObservable' = [manifestObservable EXCEPT ![e] = TRUE]
  /\ manifestMatches' = [manifestMatches EXCEPT ![e] = TRUE]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  bootstrapped, requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

LoseObservability(e) ==
  /\ e \in Epochs
  /\ manifestObservable[e]
  /\ manifestObservable' = [manifestObservable EXCEPT ![e] = FALSE]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestMatches, bootstrapped, requiredEpochs,
                  operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

BootstrapEpoch(e) ==
  /\ e \in Epochs \ bootstrapped
  /\ manifestObservable[e]
  /\ manifestMatches[e]
  /\ bootstrapped' = bootstrapped \cup {e}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

RequireEpoch(e) ==
  /\ e \in bootstrapped \ requiredEpochs
  /\ requiredEpochs' = requiredEpochs \cup {e}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

VerifyEpoch(e) ==
  /\ e \in requiredEpochs
  /\ manifestObservable[e]
  /\ manifestMatches[e]
  /\ e \notin operationalEpochs
  /\ operationalEpochs' = operationalEpochs \cup {e}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

AdvanceEpoch(e) ==
  /\ e \in requiredEpochs \cap operationalEpochs
  /\ e # activeEpoch
  /\ activeEpoch' = e
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

RemoveOldEpoch(old) ==
  /\ old \in requiredEpochs
  /\ \E e \in requiredEpochs \ {old} : e \in operationalEpochs
  /\ requiredEpochs' = requiredEpochs \ {old}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

AuthorityUpgradeProjection ==
  /\ importedLegacy # LegacyFindings
  /\ importedLegacy' = LegacyFindings
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

RemoveV4Guard ==
  /\ v4Guard
  /\ LegacyImportComplete
  /\ requiredEpochs # {}
  /\ \A e \in requiredEpochs : e \in operationalEpochs
  /\ v4Guard' = FALSE
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

RestoreV4Guard ==
  /\ ~v4Guard
  /\ v4Guard' = TRUE
  /\ v4Verified' = FALSE
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

VerifyV4 ==
  /\ v4Guard
  /\ ~v4Verified
  /\ v4Verified' = TRUE
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

AuthorityDowngradeProjection ==
  /\ v4Guard
  /\ v4Verified
  /\ ~DowngradeProjectionComplete
  /\ v4ProjectedFindings' = v4ProjectedFindings \cup V5FindingsForDowngrade
  /\ v4ProjectedCheckpoints' =
       v4ProjectedCheckpoints \cup LiveCheckpointHeads
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified,
                  positiveAudit >>

RemoveV5Requirements ==
  /\ requiredEpochs # {}
  /\ v4Guard
  /\ v4Verified
  /\ PendingRejections = {}
  /\ DowngradeProjectionComplete
  /\ requiredEpochs' = {}
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

HeadChange(pr,h) ==
  /\ pr \in prOpen
  /\ h \in Heads
  /\ h # prHead[pr]
  /\ prHead' = [prHead EXCEPT ![pr] = h]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

BaseAdvance ==
  /\ \E pr \in prOpen : baseFresh[pr]
  /\ baseFresh' =
       [pr \in PRs |-> IF pr \in prOpen THEN FALSE ELSE baseFresh[pr]]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, prHead, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

RefreshBase(pr,h) ==
  /\ pr \in prOpen
  /\ ~baseFresh[pr]
  /\ h \in Heads
  /\ h # prHead[pr]
  /\ prHead' = [prHead EXCEPT ![pr] = h]
  /\ baseFresh' = [baseFresh EXCEPT ![pr] = TRUE]
  /\ UNCHANGED << guaranteeActive,
                  prOpen, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

MergePR(pr) ==
  /\ MergeAllowed(pr)
  /\ LET h == prHead[pr]
     IN  /\ merged' = merged \cup {pr}
         /\ mergeHead' = [mergeHead EXCEPT ![pr] = h]
         /\ prOpen' = prOpen \ {pr}
  /\ UNCHANGED << guaranteeActive,
                  prHead, baseFresh,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

HumanGovernanceOverride ==
  /\ guaranteeActive
  /\ guaranteeActive' = FALSE
  /\ UNCHANGED << prOpen, prHead, baseFresh, merged, mergeHead,
                  proposalPresent, proposalCorrupt,
                  prepared, linearized, committed, dispositions, importedLegacy,
                  checkpoint,
                  gateSuccess, gateFailure, gateFresh, gateCount, poisoned,
                  activeReviews, corruptedReviews,
                  manifestObservable, manifestMatches, bootstrapped,
                  requiredEpochs, operationalEpochs, activeEpoch,
                  v4Guard, v4Verified, v4ProjectedFindings, v4ProjectedCheckpoints,
                  positiveAudit >>

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
  \/ \E e \in Epochs, h \in Heads : PoisonDuplicate(e,h)
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

Spec ==
  /\ Init
  /\ [][Next]_vars
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

Inv_NoPositiveAfterTerminalFailure ==
  \A e \in Epochs, h \in Heads :
    TerminalFailure(e,h) => ~UniqueFreshSuccess(e,h)

Inv_MergeHasNoUnresolvedDurableFinding ==
  \A pr \in PRs :
    /\ MergeAllowed(pr)
    /\ requiredEpochs # {}
    => UnresolvedDurable(prHead[pr]) = {}

Inv_MergeRequiresCheckpoint ==
  \A pr \in PRs :
    MergeAllowed(pr) => CheckpointAllows(prHead[pr])

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

Inv_NoPendingAfterV5Removal ==
  /\ guaranteeActive
  /\ requiredEpochs = {}
  => PendingRejections = {}

Inv_EpochChangeDoesNotEraseFindings ==
  AuthorityFindings = UNION {RejectionFindings[r] : r \in linearized}

(***************************************************************************)
(* REVIEW / REFINEMENT OBLIGATIONS                                         *)
(***************************************************************************)

(*
R1 Authority Ledger:
prepared, committed, dispositions, importedLegacy and V4 projections refine
append-only Git history. Protocol App may append; it must not have a bypass
allowing deletion or non-fast-forward history rewrite.

R2 Negative crash consistency:
PREPARE is durable before LinearizeNegative. A crash after Gate FAILURE but
before COMMIT must be reconstructible from PREPARE. A durable trusted negative
proposal blocks new SUCCESS even before PREPARE; once PREPARED, unresolved
pending findings continue to block new SUCCESS. PREPARE does not retroactively
erase an already fresh SUCCESS: until Gate FAILURE linearizes the negative,
a merge race is classified as late refutation by the deliberate boundary in
REVIEW.md.

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
InjectDuplicate exists to falsify recovery logic. Once detected, PoisonDuplicate
makes the pair terminally negative.

R5 Epoch:
findings are independent from activeEpoch and requiredEpochs. Governance change
never erases unresolved authority. Terminal FAILURE is scoped to an
(Epoch,Head) pair; the same Head may be reconsidered in a later epoch only after
every inherited applicable finding has an explicit disposition.

R6 Rollback:
RemoveV5Requirements is impossible until V4 is restored and verified, every
durable PREPARE has drained through negative linearization, and every
authoritative V5 finding plus every live checkpoint has a V4-compatible
projection. Candidate-specific dispositions do not retire findings at global
scope, so downgrade conservatively preserves findings that may become applicable
to future candidates. PrepareRejection is disabled while no V5 epoch is required,
so downgrade cannot be followed by a new V5-only pending rejection that V4 does
not know about.

R7 Merge:
MergePR abstracts expected_head_sha = current prHead[pr] plus strict current
base. RefreshBase creates a new Head identity, modeling the real protected-base
update that invalidates exact-candidate positive evidence. A deliberate
root-human merge outside the protocol is a governance override, not a protocol
transition.

R8 Liveness:
WF_vars(PublisherStep) abstracts periodic reconciliation. Under a stable finite
environment the publisher is expected to reconstruct after every effect and run
until quiescence. Reviewers should challenge whether this fairness assumption is
implementable.

R9 Human root:
all strong guarantees are conditioned on guaranteeActive = TRUE.
*)

=============================================================================
