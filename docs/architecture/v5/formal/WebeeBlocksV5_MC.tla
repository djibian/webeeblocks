--------------------------- MODULE WebeeBlocksV5_MC ---------------------------
EXTENDS WebeeBlocksV5

(*
Finite TLC scenarios.  These operators are substituted for the abstract
constants from WebeeBlocksV5.tla by the matching .cfg files.

Strings are used deliberately to keep counterexample traces readable.
*)

MCOwner == "OWNER"
MCExternalActor == "EXTERNAL"

MCNoLegacyCheckpointHeads == {}
MCNoStackedPRs == {}
MCNoRetryTokens == {}
MCNoRetryTokenActor == [t \in MCNoRetryTokens |-> MCOwner]
MCNoRetryTokenPR == [t \in MCNoRetryTokens |-> "P1"]
MCNoRetryTokenHead == [t \in MCNoRetryTokens |-> "H1"]
MCNoRetryTokenEpoch == [t \in MCNoRetryTokens |-> "E1"]

(***************************************************************************)
(* ORDERING: one epoch, GO/NO_GO race, repair requires a new head.         *)
(***************************************************************************)

OrderingEpochs == {"E1"}
OrderingHeads == {"H1", "H2"}
OrderingPRs == {"P1"}
OrderingProposals == {"GO_H1", "NO_H1", "DISP_F1_H2", "GO_H2"}
OrderingRejections == {"R_NO_H1"}
OrderingFindings == {"F1"}

OrderingProposalActor ==
  [p \in OrderingProposals |-> MCOwner]

OrderingProposalKind ==
  [p \in OrderingProposals |->
    CASE p = "GO_H1" -> "GO"
      [] p = "NO_H1" -> "NO_GO"
      [] p = "DISP_F1_H2" -> "DISPOSITION_RESOLVED"
      [] OTHER -> "GO"]

OrderingProposalHead ==
  [p \in OrderingProposals |->
    IF p \in {"GO_H1","NO_H1"} THEN "H1" ELSE "H2"]

OrderingProposalFinding ==
  [p \in OrderingProposals |-> "F1"]

OrderingProposalEpoch ==
  [p \in OrderingProposals |-> "E1"]

OrderingRejectionProposal ==
  [r \in OrderingRejections |-> "NO_H1"]

OrderingRejectionEpoch ==
  [r \in OrderingRejections |-> "E1"]

OrderingRejectionHead ==
  [r \in OrderingRejections |-> "H1"]

OrderingRejectionPR ==
  [r \in OrderingRejections |-> "P1"]

OrderingRejectionFindings ==
  [r \in OrderingRejections |-> {"F1"}]

OrderingApplies ==
  {<<"F1","H1">>, <<"F1","H2">>}

OrderingLegacyFindings == {}
OrderingLegacyRejectedHeads == {}
OrderingCheckpointHeads == {}
OrderingInitialPRs == {"P1"}
OrderingInitialPRHead == [p \in OrderingPRs |-> "H1"]
OrderingInitialEpoch == "E1"
OrderingFaultInjection == FALSE

(***************************************************************************)
(* EPOCH TERMINAL: E1 rejection forbids same-head resurrection in E2.      *)
(***************************************************************************)

EpochTerminalEpochs == {"E1", "E2"}
EpochTerminalHeads == {"H1"}
EpochTerminalPRs == {"P1"}
EpochTerminalProposals == {"GO_H1_E1", "NO_H1_E1", "GO_H1_E2"}
EpochTerminalRejections == {"R_NO_H1"}
EpochTerminalFindings == {"F1"}

EpochTerminalProposalActor ==
  [p \in EpochTerminalProposals |-> MCOwner]

EpochTerminalProposalKind ==
  [p \in EpochTerminalProposals |->
    IF p = "NO_H1_E1" THEN "NO_GO" ELSE "GO"]

EpochTerminalProposalHead ==
  [p \in EpochTerminalProposals |-> "H1"]

EpochTerminalProposalFinding ==
  [p \in EpochTerminalProposals |-> "F1"]

EpochTerminalProposalEpoch ==
  [p \in EpochTerminalProposals |->
    IF p = "GO_H1_E2" THEN "E2" ELSE "E1"]

EpochTerminalRejectionProposal ==
  [r \in EpochTerminalRejections |-> "NO_H1_E1"]

EpochTerminalRejectionEpoch ==
  [r \in EpochTerminalRejections |-> "E1"]

EpochTerminalRejectionHead ==
  [r \in EpochTerminalRejections |-> "H1"]

EpochTerminalRejectionPR ==
  [r \in EpochTerminalRejections |-> "P1"]

EpochTerminalRejectionFindings ==
  [r \in EpochTerminalRejections |-> {"F1"}]

EpochTerminalApplies == {<<"F1","H1">>}
EpochTerminalLegacyFindings == {}
EpochTerminalLegacyRejectedHeads == {}
EpochTerminalCheckpointHeads == {}
EpochTerminalInitialPRs == {"P1"}
EpochTerminalInitialPRHead == [p \in EpochTerminalPRs |-> "H1"]
EpochTerminalInitialEpoch == "E1"
EpochTerminalFaultInjection == FALSE

(***************************************************************************)
(* EPOCH REPAIR: inherited finding can be disposed only on new H2 in E2.   *)
(***************************************************************************)

EpochRepairEpochs == {"E1", "E2"}
EpochRepairHeads == {"H1", "H2"}
EpochRepairPRs == {"P1"}
EpochRepairProposals == {"NO_H1_E1", "DISP_F1_H2_E1", "DISP_F1_H2_E2", "GO_H2_E2"}
EpochRepairRejections == {"R_NO_H1"}
EpochRepairFindings == {"F1"}

EpochRepairProposalActor ==
  [p \in EpochRepairProposals |-> MCOwner]

EpochRepairProposalKind ==
  [p \in EpochRepairProposals |->
    CASE p = "NO_H1_E1" -> "NO_GO"
      [] p \in {"DISP_F1_H2_E1","DISP_F1_H2_E2"} -> "DISPOSITION_RESOLVED"
      [] OTHER -> "GO"]

EpochRepairProposalHead ==
  [p \in EpochRepairProposals |->
    IF p = "NO_H1_E1" THEN "H1" ELSE "H2"]

EpochRepairProposalFinding ==
  [p \in EpochRepairProposals |-> "F1"]

EpochRepairProposalEpoch ==
  [p \in EpochRepairProposals |->
    IF p \in {"NO_H1_E1","DISP_F1_H2_E1"} THEN "E1" ELSE "E2"]

EpochRepairRejectionProposal ==
  [r \in EpochRepairRejections |-> "NO_H1_E1"]

EpochRepairRejectionEpoch ==
  [r \in EpochRepairRejections |-> "E1"]

EpochRepairRejectionHead ==
  [r \in EpochRepairRejections |-> "H1"]

EpochRepairRejectionPR ==
  [r \in EpochRepairRejections |-> "P1"]

EpochRepairRejectionFindings ==
  [r \in EpochRepairRejections |-> {"F1"}]

EpochRepairApplies ==
  {<<"F1","H1">>, <<"F1","H2">>}

EpochRepairLegacyFindings == {}
EpochRepairLegacyRejectedHeads == {}
EpochRepairCheckpointHeads == {}
EpochRepairInitialPRs == {"P1"}
EpochRepairInitialPRHead == [p \in EpochRepairPRs |-> "H1"]
EpochRepairInitialEpoch == "E1"
EpochRepairFaultInjection == FALSE

(***************************************************************************)
(* DUPLICATE: positive Gate plus injected second Protocol-App writer.      *)
(***************************************************************************)

DuplicateEpochs == {"E1", "E2"}
DuplicateHeads == {"H1"}
DuplicatePRs == {"P1"}
DuplicateProposals == {"GO_H1", "NO_H1"}
DuplicateRejections == {"R_EXTERNAL"}
DuplicateFindings == {"F1"}

DuplicateProposalActor ==
  [p \in DuplicateProposals |-> MCOwner]

DuplicateProposalKind ==
  [p \in DuplicateProposals |->
    IF p = "GO_H1" THEN "GO" ELSE "NO_GO"]

DuplicateProposalHead ==
  [p \in DuplicateProposals |-> "H1"]

DuplicateProposalFinding ==
  [p \in DuplicateProposals |-> "F1"]

DuplicateProposalEpoch ==
  [p \in DuplicateProposals |-> "E1"]

DuplicateRejectionProposal ==
  [r \in DuplicateRejections |-> "NO_H1"]

DuplicateRejectionEpoch ==
  [r \in DuplicateRejections |-> "E1"]

DuplicateRejectionHead ==
  [r \in DuplicateRejections |-> "H1"]

DuplicateRejectionPR ==
  [r \in DuplicateRejections |-> "P1"]

DuplicateRejectionFindings ==
  [r \in DuplicateRejections |-> {"F1"}]

DuplicateApplies == {<<"F1","H1">>}
DuplicateLegacyFindings == {}
DuplicateLegacyRejectedHeads == {}
DuplicateCheckpointHeads == {}
DuplicateInitialPRs == {"P1"}
DuplicateInitialPRHead == [p \in DuplicatePRs |-> "H1"]
DuplicateInitialEpoch == "E1"
DuplicateFaultInjection == TRUE


(***************************************************************************)
(* PENDING HEAD: PREPARE remains blocking even when Applies is empty.      *)
(***************************************************************************)

PendingHeadEpochs == {"E1"}
PendingHeadHeads == {"H1"}
PendingHeadPRs == {"P1"}
PendingHeadProposals == {"GO_H1", "NO_H1"}
PendingHeadRejections == {"R_NO_H1"}
PendingHeadFindings == {"F1"}

PendingHeadProposalActor ==
  [p \in PendingHeadProposals |-> MCOwner]

PendingHeadProposalKind ==
  [p \in PendingHeadProposals |->
    IF p = "NO_H1" THEN "NO_GO" ELSE "GO"]

PendingHeadProposalHead ==
  [p \in PendingHeadProposals |-> "H1"]

PendingHeadProposalFinding ==
  [p \in PendingHeadProposals |-> "F1"]

PendingHeadProposalEpoch ==
  [p \in PendingHeadProposals |-> "E1"]

PendingHeadRejectionProposal ==
  [r \in PendingHeadRejections |-> "NO_H1"]

PendingHeadRejectionEpoch ==
  [r \in PendingHeadRejections |-> "E1"]

PendingHeadRejectionHead ==
  [r \in PendingHeadRejections |-> "H1"]

PendingHeadRejectionPR ==
  [r \in PendingHeadRejections |-> "P1"]

PendingHeadRejectionFindings ==
  [r \in PendingHeadRejections |-> {"F1"}]

PendingHeadApplies == {}
PendingHeadLegacyFindings == {}
PendingHeadLegacyRejectedHeads == {}
PendingHeadCheckpointHeads == {}
PendingHeadInitialPRs == {"P1"}
PendingHeadInitialPRHead == [p \in PendingHeadPRs |-> "H1"]
PendingHeadInitialEpoch == "E1"
PendingHeadFaultInjection == FALSE

(***************************************************************************)
(* SHARED HEAD: one merge must stale every other PR sharing the base.      *)
(***************************************************************************)

SharedHeadEpochs == {"E1"}
SharedHeadHeads == {"H1"}
SharedHeadPRs == {"P1", "P2"}
SharedHeadProposals == {"GO_H1", "NO_EXTERNAL"}
SharedHeadRejections == {"R_EXTERNAL"}
SharedHeadFindings == {"F1"}

SharedHeadProposalActor ==
  [p \in SharedHeadProposals |->
    IF p = "GO_H1" THEN MCOwner ELSE MCExternalActor]

SharedHeadProposalKind ==
  [p \in SharedHeadProposals |->
    IF p = "GO_H1" THEN "GO" ELSE "NO_GO"]

SharedHeadProposalHead ==
  [p \in SharedHeadProposals |-> "H1"]

SharedHeadProposalFinding ==
  [p \in SharedHeadProposals |-> "F1"]

SharedHeadProposalEpoch ==
  [p \in SharedHeadProposals |-> "E1"]

SharedHeadRejectionProposal ==
  [r \in SharedHeadRejections |-> "NO_EXTERNAL"]

SharedHeadRejectionEpoch ==
  [r \in SharedHeadRejections |-> "E1"]

SharedHeadRejectionHead ==
  [r \in SharedHeadRejections |-> "H1"]

SharedHeadRejectionPR ==
  [r \in SharedHeadRejections |-> "P1"]

SharedHeadRejectionFindings ==
  [r \in SharedHeadRejections |-> {"F1"}]

SharedHeadApplies == {}
SharedHeadLegacyFindings == {}
SharedHeadLegacyRejectedHeads == {}
SharedHeadCheckpointHeads == {}
SharedHeadInitialPRs == {"P1", "P2"}
SharedHeadInitialPRHead == [p \in SharedHeadPRs |-> "H1"]
SharedHeadInitialEpoch == "E1"
SharedHeadFaultInjection == FALSE

(***************************************************************************)
(* LATE REFUTATION: merge-wins race must block subsequent V5 integration.  *)
(***************************************************************************)

LateEpochs == {"E1"}
LateHeads == {"H1", "H2", "H3"}
LatePRs == {"P1", "P2"}
LateProposals == {"GO_H1", "NO_H1", "GO_H3"}
LateRejections == {"R_NO_H1"}
LateFindings == {"F1"}

LateProposalActor ==
  [p \in LateProposals |-> MCOwner]

LateProposalKind ==
  [p \in LateProposals |->
    IF p = "NO_H1" THEN "NO_GO" ELSE "GO"]

LateProposalHead ==
  [p \in LateProposals |->
    CASE p = "GO_H1" -> "H1"
      [] p = "NO_H1" -> "H1"
      [] OTHER -> "H3"]

LateProposalFinding ==
  [p \in LateProposals |-> "F1"]

LateProposalEpoch ==
  [p \in LateProposals |-> "E1"]

LateRejectionProposal ==
  [r \in LateRejections |-> "NO_H1"]

LateRejectionEpoch ==
  [r \in LateRejections |-> "E1"]

LateRejectionHead ==
  [r \in LateRejections |-> "H1"]

LateRejectionPR ==
  [r \in LateRejections |-> "P1"]

LateRejectionFindings ==
  [r \in LateRejections |-> {"F1"}]

LateApplies ==
  {<<"F1","H1">>}

LateLegacyFindings == {}
LateLegacyRejectedHeads == {}
LateCheckpointHeads == {}
LateInitialPRs == {"P1", "P2"}
LateInitialPRHead ==
  [p \in LatePRs |-> IF p = "P1" THEN "H1" ELSE "H2"]
LateInitialEpoch == "E1"
LateFaultInjection == FALSE

(*
Focused transition relation for the late-refutation safety domain.

This deliberately preserves the complete merge-wins attack:
V5 bootstrap -> GO(H1) -> SUCCESS(H1) -> recoverable Publisher merge(P1) ->
late NO_GO(H1) -> rejection linearization/trunk block -> refresh P2 to H3 ->
GO(H3) -> attempted later Publisher merge.

It excludes orthogonal governance drift, rollback, review mutation, duplicate,
checkpoint and arbitrary HeadChange transitions that are exercised by their
own finite domains.  It does not constrain trunkBlocked, MergeAllowed, merged,
negative authority, or any invariant under test.
*)
LateRefutationNext ==
  \/ \E p \in LateProposals : PublishProposal(p)
  \/ ConfigureEpoch("E1")
  \/ BootstrapEpoch("E1")
  \/ RequireEpoch("E1")
  \/ VerifyEpoch("E1")
  \/ PublishSuccess("GO_H1", "E1", "H1")
  \/ PrepareRejection("R_NO_H1")
  \/ LinearizeNegative("R_NO_H1")
  \/ CommitRejection("R_NO_H1")
  \/ \E pr \in LatePRs : PreparePublisherMerge(pr)
  \/ \E pr \in LatePRs : SubmitPublisherMerge(pr)
  \/ \E pr \in LatePRs : CancelPreparedMerge(pr)
  \/ \E pr \in LatePRs : RemoteMergeLinearizeSuccess(pr)
  \/ \E pr \in LatePRs : RemoteMergeLinearizeFailure(pr)
  \/ \E pr \in LatePRs : ObserveRemoteMergeSuccess(pr)
  \/ \E pr \in LatePRs : ObserveRemoteMergeFailure(pr)
  \/ \E pr \in LatePRs : CommitPublisherMerge(pr)
  \/ RefreshBase("P2", "H3")
  \/ PublishSuccess("GO_H3", "E1", "H3")

(***************************************************************************)
(* CHECKPOINT: PASS -> SUCCESS -> HUMAN_FAIL must revoke monotonically.     *)
(***************************************************************************)

CheckpointEpochs == {"E1"}
CheckpointHeadsUniverse == {"H1", "H2"}
CheckpointPRs == {"P1"}
CheckpointProposals == {"PASS_H1", "GO_H1", "FAIL_H1", "DISP_F1_H2", "GO_H2"}
CheckpointRejections == {"R_FAIL_H1"}
CheckpointFindings == {"F1"}

CheckpointProposalActor ==
  [p \in CheckpointProposals |-> MCOwner]

CheckpointProposalKind ==
  [p \in CheckpointProposals |->
    CASE p = "PASS_H1" -> "HUMAN_PASS"
      [] p = "GO_H1" -> "GO"
      [] p = "FAIL_H1" -> "HUMAN_FAIL"
      [] p = "DISP_F1_H2" -> "DISPOSITION_RESOLVED"
      [] OTHER -> "GO"]

CheckpointProposalHead ==
  [p \in CheckpointProposals |->
    IF p \in {"PASS_H1","GO_H1","FAIL_H1"} THEN "H1" ELSE "H2"]

CheckpointProposalFinding ==
  [p \in CheckpointProposals |-> "F1"]

CheckpointProposalEpoch ==
  [p \in CheckpointProposals |-> "E1"]

CheckpointRejectionProposal ==
  [r \in CheckpointRejections |-> "FAIL_H1"]

CheckpointRejectionEpoch ==
  [r \in CheckpointRejections |-> "E1"]

CheckpointRejectionHead ==
  [r \in CheckpointRejections |-> "H1"]

CheckpointRejectionPR ==
  [r \in CheckpointRejections |-> "P1"]

CheckpointRejectionFindings ==
  [r \in CheckpointRejections |-> {"F1"}]

CheckpointApplies ==
  {<<"F1","H1">>, <<"F1","H2">>}

CheckpointLegacyFindings == {}
CheckpointLegacyRejectedHeads == {}
CheckpointRequiredHeads == {"H1"}
CheckpointInitialPRs == {"P1"}
CheckpointInitialPRHead == [p \in CheckpointPRs |-> "H1"]
CheckpointInitialEpoch == "E1"
CheckpointFaultInjection == FALSE

(***************************************************************************)
(* MIGRATION: legacy authority import + V5 terminal state downgrade.        *)
(***************************************************************************)

MigrationEpochs == {"E1"}
MigrationHeads == {"H1", "H2"}
MigrationPRs == {"P1"}
MigrationProposals ==
  {"DISP_LEGACY_H2", "GO_H2", "NO_H2", "DISP_V5_H1", "PASS_H1"}
MigrationRejections == {"R_NO_H2"}
MigrationFindings == {"F_LEGACY", "F_V5"}

MigrationProposalActor ==
  [p \in MigrationProposals |-> MCOwner]

MigrationProposalKind ==
  [p \in MigrationProposals |->
    CASE p = "DISP_LEGACY_H2" -> "DISPOSITION_RESOLVED"
      [] p = "GO_H2" -> "GO"
      [] p = "NO_H2" -> "NO_GO"
      [] p = "PASS_H1" -> "HUMAN_PASS"
      [] OTHER -> "DISPOSITION_RESOLVED"]

MigrationProposalHead ==
  [p \in MigrationProposals |->
    IF p \in {"DISP_LEGACY_H2","GO_H2","NO_H2"} THEN "H2" ELSE "H1"]

MigrationProposalFinding ==
  [p \in MigrationProposals |->
    IF p = "DISP_LEGACY_H2" THEN "F_LEGACY" ELSE "F_V5"]

MigrationProposalEpoch ==
  [p \in MigrationProposals |-> "E1"]

MigrationRejectionProposal ==
  [r \in MigrationRejections |-> "NO_H2"]

MigrationRejectionEpoch ==
  [r \in MigrationRejections |-> "E1"]

MigrationRejectionHead ==
  [r \in MigrationRejections |-> "H2"]

MigrationRejectionPR ==
  [r \in MigrationRejections |-> "P1"]

MigrationRejectionFindings ==
  [r \in MigrationRejections |-> {"F_V5"}]

MigrationApplies ==
  {<<"F_LEGACY","H1">>, <<"F_LEGACY","H2">>,
   <<"F_V5","H1">>, <<"F_V5","H2">>}

MigrationLegacyFindings == {"F_LEGACY"}
MigrationLegacyRejectedHeads == {"H1"}
MigrationCheckpointHeads == {"H1"}
MigrationInitialPRs == {"P1"}
MigrationInitialPRHead == [p \in MigrationPRs |-> "H2"]
MigrationInitialEpoch == "E1"
MigrationFaultInjection == FALSE

(***************************************************************************)
(* MERGE IN FLIGHT: remote outcome must resolve before later authority.     *)
(***************************************************************************)

MergeFlightEpochs == {"E1", "E2"}
MergeFlightHeads == {"H1", "H2"}
MergeFlightPRs == {"P1", "P2"}
MergeFlightProposals == {"GO_H1", "NO_H2"}
MergeFlightRejections == {"R_NO_H2"}
MergeFlightFindings == {"F1"}

MergeFlightProposalActor ==
  [p \in MergeFlightProposals |-> MCOwner]

MergeFlightProposalKind ==
  [p \in MergeFlightProposals |->
    IF p = "NO_H2" THEN "NO_GO" ELSE "GO"]

MergeFlightProposalHead ==
  [p \in MergeFlightProposals |->
    IF p = "NO_H2" THEN "H2" ELSE "H1"]

MergeFlightProposalFinding ==
  [p \in MergeFlightProposals |-> "F1"]

MergeFlightProposalEpoch ==
  [p \in MergeFlightProposals |-> "E1"]

MergeFlightRejectionProposal ==
  [r \in MergeFlightRejections |-> "NO_H2"]

MergeFlightRejectionEpoch ==
  [r \in MergeFlightRejections |-> "E1"]

MergeFlightRejectionHead ==
  [r \in MergeFlightRejections |-> "H2"]

MergeFlightRejectionPR ==
  [r \in MergeFlightRejections |-> "P2"]

MergeFlightRejectionFindings ==
  [r \in MergeFlightRejections |-> {"F1"}]

MergeFlightApplies == {<<"F1","H2">>}
MergeFlightLegacyFindings == {}
MergeFlightLegacyRejectedHeads == {}
MergeFlightCheckpointHeads == {}
MergeFlightInitialPRs == {"P1", "P2"}
MergeFlightInitialPRHead ==
  [p \in MergeFlightPRs |-> IF p = "P1" THEN "H1" ELSE "H2"]
MergeFlightInitialEpoch == "E1"
MergeFlightFaultInjection == FALSE

(*
Focused transition relation for the submitted-merge governance attack.

It preserves both high-value races:
1. P1 is authorized under E1, submitted, E2 becomes required without any E2
   SUCCESS, then GitHub attempts remote SUCCESS/FAILURE.
2. A trusted NO_GO for unrelated P2 may arrive while P1 is outstanding; the
   Publisher barrier must prevent its rejection authority from overtaking P1
   until the merge transaction is terminally observed and committed.

It also permits E1 Gate expiry, governance drift and observability loss after
SUBMIT.  It excludes rollback, review, duplicate, checkpoint and arbitrary PR
mutations covered by other domains.  It does not constrain MergeAllowed,
requiredEpochs, Gate state, manifest health, remote outcome or any invariant
under test.
*)
MergeFlightPublisherStep ==
  /\ ~v5Retired
  /\ IF MergeTransactionIdle
        THEN \/ PublishSuccess("GO_H1", "E1", "H1")
             \/ PrepareRejection("R_NO_H2")
             \/ LinearizeNegative("R_NO_H2")
             \/ CommitRejection("R_NO_H2")
             \/ PreparePublisherMerge("P1")
        ELSE \/ SubmitPublisherMerge("P1")
             \/ CancelPreparedMerge("P1")
             \/ ObserveRemoteMergeSuccess("P1")
             \/ ObserveRemoteMergeFailure("P1")
             \/ CommitPublisherMerge("P1")

MergeFlightNext ==
  \/ MergeFlightPublisherStep
  \/ PublishProposal("GO_H1")
  \/ PublishProposal("NO_H2")
  \/ ConfigureEpoch("E1")
  \/ BootstrapEpoch("E1")
  \/ RequireEpoch("E1")
  \/ VerifyEpoch("E1")
  \/ ConfigureEpoch("E2")
  \/ BootstrapEpoch("E2")
  \/ RequireEpoch("E2")
  \/ VerifyEpoch("E2")
  \/ ExpireSuccess("E1", "H1")
  \/ LoseObservability("E1")
  \/ DriftGovernance("E1")
  \/ LoseObservability("E2")
  \/ DriftGovernance("E2")
  \/ RemoteMergeLinearizeSuccess("P1")
  \/ RemoteMergeLinearizeFailure("P1")

(***************************************************************************)
(* MERGE RETRY: failed/cancelled attempt may be explicitly retried.        *)
(***************************************************************************)

MergeRetryEpochs == {"E1"}
MergeRetryHeads == {"H1", "H2"}
MergeRetryPRs == {"P1"}
MergeRetryProposals == {"GO_H1", "GO_H2", "EXT_NO"}
MergeRetryRejections == {"R_EXT"}
MergeRetryFindings == {"F1"}
MergeRetryProposalActor == [p \in MergeRetryProposals |-> IF p = "EXT_NO" THEN MCExternalActor ELSE MCOwner]
MergeRetryProposalKind == [p \in MergeRetryProposals |-> IF p = "EXT_NO" THEN "NO_GO" ELSE "GO"]
MergeRetryProposalHead == [p \in MergeRetryProposals |-> IF p = "GO_H2" THEN "H2" ELSE "H1"]
MergeRetryProposalFinding == [p \in MergeRetryProposals |-> "F1"]
MergeRetryProposalEpoch == [p \in MergeRetryProposals |-> "E1"]
MergeRetryRejectionProposal == [r \in MergeRetryRejections |-> "EXT_NO"]
MergeRetryRejectionEpoch == [r \in MergeRetryRejections |-> "E1"]
MergeRetryRejectionHead == [r \in MergeRetryRejections |-> "H1"]
MergeRetryRejectionPR == [r \in MergeRetryRejections |-> "P1"]
MergeRetryRejectionFindings == [r \in MergeRetryRejections |-> {"F1"}]
MergeRetryApplies == {}
MergeRetryLegacyFindings == {}
MergeRetryLegacyRejectedHeads == {}
MergeRetryRetryTokens == {"T1", "T2", "T3"}
MergeRetryRetryTokenActor == [t \in MergeRetryRetryTokens |-> MCOwner]
MergeRetryRetryTokenPR == [t \in MergeRetryRetryTokens |-> "P1"]
MergeRetryRetryTokenHead == [t \in MergeRetryRetryTokens |-> IF t = "T3" THEN "H2" ELSE "H1"]
MergeRetryRetryTokenEpoch == [t \in MergeRetryRetryTokens |-> "E1"]
MergeRetryCheckpointHeads == {}
MergeRetryInitialPRs == {"P1"}
MergeRetryInitialPRHead == [p \in MergeRetryPRs |-> "H1"]
MergeRetryInitialEpoch == "E1"
MergeRetryFaultInjection == FALSE

MergeRetryNext ==
  \/ \E p \in MergeRetryProposals : PublishProposal(p)
  \/ ConfigureEpoch("E1")
  \/ BootstrapEpoch("E1")
  \/ RequireEpoch("E1")
  \/ VerifyEpoch("E1")
  \/ PublishSuccess("GO_H1", "E1", "H1")
  \/ PublishSuccess("GO_H2", "E1", "H2")
  \/ PreparePublisherMerge("P1")
  \/ SubmitPublisherMerge("P1")
  \/ CancelPreparedMerge("P1")
  \/ RemoteMergeLinearizeSuccess("P1")
  \/ RemoteMergeLinearizeFailure("P1")
  \/ ObserveRemoteMergeSuccess("P1")
  \/ ObserveRemoteMergeFailure("P1")
  \/ CommitPublisherMerge("P1")
  \/ PublishRetryAuthorization("T1")
  \/ PublishRetryAuthorization("T2")
  \/ PublishRetryAuthorization("T3")
  \/ HeadChange("P1", "H2")

(***************************************************************************)
(* STACK EXCLUSION: normal V5 async merge is single-PR only.                *)
(***************************************************************************)

StackExclusionEpochs == {"E1"}
StackExclusionHeads == {"H1"}
StackExclusionPRs == {"P1"}
StackExclusionProposals == {"GO_H1", "NO_H1"}
StackExclusionRejections == {"R_NO_H1"}
StackExclusionFindings == {"F1"}
StackExclusionProposalActor == [p \in StackExclusionProposals |-> MCOwner]
StackExclusionProposalKind == [p \in StackExclusionProposals |-> IF p = "GO_H1" THEN "GO" ELSE "NO_GO"]
StackExclusionProposalHead == [p \in StackExclusionProposals |-> "H1"]
StackExclusionProposalFinding == [p \in StackExclusionProposals |-> "F1"]
StackExclusionProposalEpoch == [p \in StackExclusionProposals |-> "E1"]
StackExclusionRejectionProposal == [r \in StackExclusionRejections |-> "NO_H1"]
StackExclusionRejectionEpoch == [r \in StackExclusionRejections |-> "E1"]
StackExclusionRejectionHead == [r \in StackExclusionRejections |-> "H1"]
StackExclusionRejectionPR == [r \in StackExclusionRejections |-> "P1"]
StackExclusionRejectionFindings == [r \in StackExclusionRejections |-> {"F1"}]
StackExclusionApplies == {}
StackExclusionLegacyFindings == {}
StackExclusionLegacyRejectedHeads == {}
StackExclusionLegacyCheckpointHeads == {}
StackExclusionStackedPRs == {"P1"}
StackExclusionCheckpointHeads == {}
StackExclusionInitialPRs == {"P1"}
StackExclusionInitialPRHead == [p \in StackExclusionPRs |-> "H1"]
StackExclusionInitialEpoch == "E1"
StackExclusionFaultInjection == FALSE

StackExclusionNext ==
  \/ AuthorityUpgradeProjection
  \/ PublishProposal("GO_H1")
  \/ ConfigureEpoch("E1")
  \/ BootstrapEpoch("E1")
  \/ RequireEpoch("E1")
  \/ VerifyEpoch("E1")
  \/ PublishSuccess("GO_H1", "E1", "H1")
  \/ PreparePublisherMerge("P1")

(***************************************************************************)
(* LEGACY CHECKPOINT CUTOVER: unresolved V4 TEST_REQUIRED blocks V5.       *)
(***************************************************************************)

LegacyCheckpointEpochs == {"E1"}
LegacyCheckpointHeadsSet == {"H1"}
LegacyCheckpointPRs == {"P1"}
LegacyCheckpointProposals == {"GO_H1", "NO_H1"}
LegacyCheckpointRejections == {"R_NO_H1"}
LegacyCheckpointFindings == {"F1"}
LegacyCheckpointProposalActor == [p \in LegacyCheckpointProposals |-> MCOwner]
LegacyCheckpointProposalKind == [p \in LegacyCheckpointProposals |-> IF p = "GO_H1" THEN "GO" ELSE "NO_GO"]
LegacyCheckpointProposalHead == [p \in LegacyCheckpointProposals |-> "H1"]
LegacyCheckpointProposalFinding == [p \in LegacyCheckpointProposals |-> "F1"]
LegacyCheckpointProposalEpoch == [p \in LegacyCheckpointProposals |-> "E1"]
LegacyCheckpointRejectionProposal == [r \in LegacyCheckpointRejections |-> "NO_H1"]
LegacyCheckpointRejectionEpoch == [r \in LegacyCheckpointRejections |-> "E1"]
LegacyCheckpointRejectionHead == [r \in LegacyCheckpointRejections |-> "H1"]
LegacyCheckpointRejectionPR == [r \in LegacyCheckpointRejections |-> "P1"]
LegacyCheckpointRejectionFindings == [r \in LegacyCheckpointRejections |-> {"F1"}]
LegacyCheckpointApplies == {}
LegacyCheckpointLegacyFindings == {}
LegacyCheckpointLegacyRejectedHeads == {}
LegacyCheckpointLegacyCheckpointHeads == {"H1"}
LegacyCheckpointCheckpointHeads == {"H1"}
LegacyCheckpointInitialPRs == {"P1"}
LegacyCheckpointInitialPRHead == [p \in LegacyCheckpointPRs |-> "H1"]
LegacyCheckpointInitialEpoch == "E1"
LegacyCheckpointFaultInjection == FALSE

LegacyCheckpointNext ==
  \/ AuthorityUpgradeProjection
  \/ ConfigureEpoch("E1")
  \/ BootstrapEpoch("E1")
  \/ RequireEpoch("E1")
  \/ VerifyEpoch("E1")
  \/ PublishProposal("GO_H1")
  \/ PublishSuccess("GO_H1", "E1", "H1")
  \/ RemoveV4Guard

(***************************************************************************)
(* RETIRED REPLAY: V5-only seen-head memory cannot govern restored V4.      *)
(***************************************************************************)

RetiredReplayEpochs == {"E1"}
RetiredReplayHeads == {"H1", "H2"}
RetiredReplayPRs == {"P1"}
RetiredReplayProposals == {"GO_H2", "NO_H1"}
RetiredReplayRejections == {"R_NO_H1"}
RetiredReplayFindings == {"F1"}
RetiredReplayProposalActor == [p \in RetiredReplayProposals |-> MCOwner]
RetiredReplayProposalKind == [p \in RetiredReplayProposals |-> IF p = "GO_H2" THEN "GO" ELSE "NO_GO"]
RetiredReplayProposalHead == [p \in RetiredReplayProposals |-> IF p = "GO_H2" THEN "H2" ELSE "H1"]
RetiredReplayProposalFinding == [p \in RetiredReplayProposals |-> "F1"]
RetiredReplayProposalEpoch == [p \in RetiredReplayProposals |-> "E1"]
RetiredReplayRejectionProposal == [r \in RetiredReplayRejections |-> "NO_H1"]
RetiredReplayRejectionEpoch == [r \in RetiredReplayRejections |-> "E1"]
RetiredReplayRejectionHead == [r \in RetiredReplayRejections |-> "H1"]
RetiredReplayRejectionPR == [r \in RetiredReplayRejections |-> "P1"]
RetiredReplayRejectionFindings == [r \in RetiredReplayRejections |-> {"F1"}]
RetiredReplayApplies == {}
RetiredReplayLegacyFindings == {}
RetiredReplayLegacyRejectedHeads == {}
RetiredReplayLegacyCheckpointHeads == {}
RetiredReplayCheckpointHeads == {}
RetiredReplayInitialPRs == {"P1"}
RetiredReplayInitialPRHead == [p \in RetiredReplayPRs |-> "H1"]
RetiredReplayInitialEpoch == "E1"
RetiredReplayFaultInjection == FALSE

RetiredReplayNext ==
  \/ AuthorityUpgradeProjection
  \/ ConfigureEpoch("E1")
  \/ BootstrapEpoch("E1")
  \/ RequireEpoch("E1")
  \/ VerifyEpoch("E1")
  \/ PublishProposal("GO_H2")
  \/ RemoveV5Requirements
  \/ HeadChange("P1", "H2")

(***************************************************************************)
(* ABANDON: rejected PR may close without semantically resolving findings. *)
(***************************************************************************)

AbandonEpochs == {"E1"}
AbandonHeads == {"H1"}
AbandonPRs == {"P1"}
AbandonProposals == {"NO_H1"}
AbandonRejections == {"R_NO_H1"}
AbandonFindings == {"F1"}

AbandonProposalActor ==
  [p \in AbandonProposals |-> MCOwner]

AbandonProposalKind ==
  [p \in AbandonProposals |-> "NO_GO"]

AbandonProposalHead ==
  [p \in AbandonProposals |-> "H1"]

AbandonProposalFinding ==
  [p \in AbandonProposals |-> "F1"]

AbandonProposalEpoch ==
  [p \in AbandonProposals |-> "E1"]

AbandonRejectionProposal ==
  [r \in AbandonRejections |-> "NO_H1"]

AbandonRejectionEpoch ==
  [r \in AbandonRejections |-> "E1"]

AbandonRejectionHead ==
  [r \in AbandonRejections |-> "H1"]

AbandonRejectionPR ==
  [r \in AbandonRejections |-> "P1"]

AbandonRejectionFindings ==
  [r \in AbandonRejections |-> {"F1"}]

AbandonApplies == {<<"F1","H1">>}
AbandonLegacyFindings == {}
AbandonLegacyRejectedHeads == {}
AbandonCheckpointHeads == {}
AbandonInitialPRs == {"P1"}
AbandonInitialPRHead == [p \in AbandonPRs |-> "H1"]
AbandonInitialEpoch == "E1"
AbandonFaultInjection == FALSE

(***************************************************************************)
(* CHECKPOINT EPOCH: E1 human PASS must not authorize E2.                  *)
(***************************************************************************)

CheckpointEpochEpochs == {"E1", "E2"}
CheckpointEpochHeads == {"H1"}
CheckpointEpochPRs == {"P1"}
CheckpointEpochProposals ==
  {"PASS_E1", "GO_E1", "PASS_E2", "GO_E2", "NO_EXTERNAL"}
CheckpointEpochRejections == {"R_EXTERNAL"}
CheckpointEpochFindings == {"F1"}

CheckpointEpochProposalActor ==
  [p \in CheckpointEpochProposals |->
    IF p = "NO_EXTERNAL" THEN MCExternalActor ELSE MCOwner]

CheckpointEpochProposalKind ==
  [p \in CheckpointEpochProposals |->
    CASE p \in {"PASS_E1","PASS_E2"} -> "HUMAN_PASS"
      [] p = "NO_EXTERNAL" -> "NO_GO"
      [] OTHER -> "GO"]

CheckpointEpochProposalHead ==
  [p \in CheckpointEpochProposals |-> "H1"]

CheckpointEpochProposalFinding ==
  [p \in CheckpointEpochProposals |-> "F1"]

CheckpointEpochProposalEpoch ==
  [p \in CheckpointEpochProposals |->
    IF p \in {"PASS_E2","GO_E2"} THEN "E2" ELSE "E1"]

CheckpointEpochRejectionProposal ==
  [r \in CheckpointEpochRejections |-> "NO_EXTERNAL"]

CheckpointEpochRejectionEpoch ==
  [r \in CheckpointEpochRejections |-> "E1"]

CheckpointEpochRejectionHead ==
  [r \in CheckpointEpochRejections |-> "H1"]

CheckpointEpochRejectionPR ==
  [r \in CheckpointEpochRejections |-> "P1"]

CheckpointEpochRejectionFindings ==
  [r \in CheckpointEpochRejections |-> {"F1"}]

CheckpointEpochApplies == {}
CheckpointEpochLegacyFindings == {}
CheckpointEpochLegacyRejectedHeads == {}
CheckpointEpochRequiredHeads == {"H1"}
CheckpointEpochInitialPRs == {"P1"}
CheckpointEpochInitialPRHead == [p \in CheckpointEpochPRs |-> "H1"]
CheckpointEpochInitialEpoch == "E1"
CheckpointEpochFaultInjection == FALSE

(***************************************************************************)
(* EXTERNAL EVIDENCE: external proposal must not reserve a future HEAD.    *)
(***************************************************************************)

ExternalEvidenceEpochs == {"E1"}
ExternalEvidenceHeads == {"H1", "H2"}
ExternalEvidencePRs == {"P1"}
ExternalEvidenceProposals == {"GO_H1", "EXT_H2"}
ExternalEvidenceRejections == {"R_EXT_H2"}
ExternalEvidenceFindings == {"F1"}

ExternalEvidenceProposalActor ==
  [p \in ExternalEvidenceProposals |->
    IF p = "EXT_H2" THEN MCExternalActor ELSE MCOwner]

ExternalEvidenceProposalKind ==
  [p \in ExternalEvidenceProposals |->
    IF p = "EXT_H2" THEN "NO_GO" ELSE "GO"]

ExternalEvidenceProposalHead ==
  [p \in ExternalEvidenceProposals |->
    IF p = "EXT_H2" THEN "H2" ELSE "H1"]

ExternalEvidenceProposalFinding ==
  [p \in ExternalEvidenceProposals |-> "F1"]

ExternalEvidenceProposalEpoch ==
  [p \in ExternalEvidenceProposals |-> "E1"]

ExternalEvidenceRejectionProposal ==
  [r \in ExternalEvidenceRejections |-> "EXT_H2"]

ExternalEvidenceRejectionEpoch ==
  [r \in ExternalEvidenceRejections |-> "E1"]

ExternalEvidenceRejectionHead ==
  [r \in ExternalEvidenceRejections |-> "H2"]

ExternalEvidenceRejectionPR ==
  [r \in ExternalEvidenceRejections |-> "P1"]

ExternalEvidenceRejectionFindings ==
  [r \in ExternalEvidenceRejections |-> {"F1"}]

ExternalEvidenceApplies == {}
ExternalEvidenceLegacyFindings == {}
ExternalEvidenceLegacyRejectedHeads == {}
ExternalEvidenceCheckpointHeads == {}
ExternalEvidenceInitialPRs == {"P1"}
ExternalEvidenceInitialPRHead == [p \in ExternalEvidencePRs |-> "H1"]
ExternalEvidenceInitialEpoch == "E1"
ExternalEvidenceFaultInjection == FALSE

(***************************************************************************)
(* FOCUS CONSTRAINT: non-merge scenarios exclude V5 merge preparation.     *)
(***************************************************************************)

NoV5MergeConstraint ==
  mergePrepared = {}


=============================================================================
