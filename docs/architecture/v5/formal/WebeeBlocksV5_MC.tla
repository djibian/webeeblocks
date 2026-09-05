--------------------------- MODULE WebeeBlocksV5_MC ---------------------------
EXTENDS WebeeBlocksV5

(*
Finite TLC scenarios.  These operators are substituted for the abstract
constants from WebeeBlocksV5.tla by the matching .cfg files.

Strings are used deliberately to keep counterexample traces readable.
*)

MCOwner == "OWNER"
MCExternalActor == "EXTERNAL"

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

DuplicateEpochs == {"E1"}
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
  {"DISP_LEGACY_H2", "GO_H2", "NO_H2", "DISP_V5_H1"}
MigrationRejections == {"R_NO_H2"}
MigrationFindings == {"F_LEGACY", "F_V5"}

MigrationProposalActor ==
  [p \in MigrationProposals |-> MCOwner]

MigrationProposalKind ==
  [p \in MigrationProposals |->
    CASE p = "DISP_LEGACY_H2" -> "DISPOSITION_RESOLVED"
      [] p = "GO_H2" -> "GO"
      [] p = "NO_H2" -> "NO_GO"
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
MigrationCheckpointHeads == {}
MigrationInitialPRs == {"P1"}
MigrationInitialPRHead == [p \in MigrationPRs |-> "H2"]
MigrationInitialEpoch == "E1"
MigrationFaultInjection == FALSE

=============================================================================
