#!/usr/bin/env python3
"""Host-first post-reset teacher binding decision on the existing trusted socket.

This is a no-effect protocol prerequisite for the #287 physical-run composition.
After #266 has established a genuinely new live connection epoch, the trusted
physical host already owns the exact non-authority profile/canonical-AST binding
that must be approved. The teacher peer must not guess that host-minted epoch.

``PostResetTeacherDecisionChannel`` therefore reuses the exact launcher-installed
socket and fail-closed machinery from #288, but the host sends the exact binding
proposal first. A correlated explicit teacher decision still mints the existing
#267 process-local receipt through ``TrustedTeacherAuthorizer``. The proposal and
decision remain ``executionAuthority:false`` data; neither message is a physical
effect capability.
"""

from __future__ import annotations

import secrets

from teacher_decision_channel import (
    TeacherDecisionChannelError,
    TrustedTeacherDecisionChannel,
    _read_epoch,
    _require_timeout,
)
from teacher_run_authorization import (
    PhysicalRunBinding,
    TeacherRunAuthorization,
    TeacherRunAuthorizationError,
    TrustedTeacherAuthorizer,
)


class PostResetTeacherDecisionChannel(TrustedTeacherDecisionChannel):
    """One host-first exact-binding decision on the #288 trusted socket."""

    def receive_authorization_for_binding(
        self,
        authorizer: TrustedTeacherAuthorizer,
        binding: PhysicalRunBinding,
        *,
        decision_timeout_seconds: float = 5.0,
    ) -> TeacherRunAuthorization:
        """Publish one host-owned post-reset binding, then require explicit approval."""
        if type(authorizer) is not TrustedTeacherAuthorizer:
            raise TeacherDecisionChannelError(
                "exact trusted teacher authorizer is required"
            )
        if type(binding) is not PhysicalRunBinding:
            raise TeacherDecisionChannelError(
                "exact host-owned physical run binding is required"
            )
        timeout = _require_timeout(decision_timeout_seconds)

        with self._lock:
            if self._terminal:
                raise TeacherDecisionChannelError(
                    "teacher decision channel is terminal: "
                    + (self._terminal_reason or "prior decision consumed")
                )
            if self._started:
                raise TeacherDecisionChannelError(
                    "teacher decision channel already has an active exchange"
                )
            self._started = True

        receipt: TeacherRunAuthorization | None = None
        try:
            before_epoch = _read_epoch(self._epoch_reader)
            if binding.connection_epoch != before_epoch:
                raise TeacherDecisionChannelError(
                    "host teacher binding does not match the live connection epoch"
                )

            request_id = secrets.token_urlsafe(24)
            challenge_id = self._challenge_id()
            proposal = {
                "op": "teacher-run-binding-proposal",
                "requestId": request_id,
                "challengeId": challenge_id,
                "profileId": binding.profile_id,
                "astBinding": binding.ast_binding,
                "connectionEpoch": binding.connection_epoch,
                "executionAuthority": False,
            }
            self._send_json_line(proposal, timeout)
            response = self._recv_json_line(timeout)

            if set(response) != {
                "op",
                "requestId",
                "challengeId",
                "profileId",
                "astBinding",
                "connectionEpoch",
                "approved",
                "executionAuthority",
            }:
                raise TeacherDecisionChannelError(
                    "teacher decision reply has unsupported fields"
                )
            if response.get("op") != "teacher-run-decision-result":
                raise TeacherDecisionChannelError(
                    "teacher decision reply has the wrong operation"
                )
            if response.get("requestId") != request_id:
                raise TeacherDecisionChannelError(
                    "teacher decision reply has the wrong request correlation"
                )
            if response.get("challengeId") != challenge_id:
                raise TeacherDecisionChannelError(
                    "teacher decision reply has the wrong challenge correlation"
                )
            if response.get("executionAuthority") is not False:
                raise TeacherDecisionChannelError(
                    "teacher decision transport must remain non-authority data"
                )
            if (
                response.get("profileId") != binding.profile_id
                or response.get("astBinding") != binding.ast_binding
                or response.get("connectionEpoch") != binding.connection_epoch
            ):
                raise TeacherDecisionChannelError(
                    "teacher decision reply does not match the host-proposed run binding"
                )
            approved = response.get("approved")
            if not isinstance(approved, bool):
                raise TeacherDecisionChannelError(
                    "teacher decision reply must contain a boolean approved value"
                )

            if _read_epoch(self._epoch_reader) != before_epoch:
                raise TeacherDecisionChannelError(
                    "connection epoch changed during teacher decision"
                )
            if approved is not True:
                raise TeacherDecisionChannelError(
                    "teacher explicitly denied this physical run"
                )

            self._require_peer_write_closed(timeout)
            if _read_epoch(self._epoch_reader) != before_epoch:
                raise TeacherDecisionChannelError(
                    "connection epoch changed while sealing teacher decision"
                )

            try:
                receipt = authorizer.authorize_run(
                    binding,
                    lambda exact_binding: exact_binding == binding,
                )
            except TeacherRunAuthorizationError as exc:
                raise TeacherDecisionChannelError(
                    "teacher authorization receipt could not be minted"
                ) from exc

            if _read_epoch(self._epoch_reader) != before_epoch:
                try:
                    authorizer.close_run(
                        receipt,
                        "connection epoch changed while minting teacher authorization",
                    )
                except TeacherRunAuthorizationError:
                    receipt.invalidate(
                        "connection epoch changed while minting teacher authorization"
                    )
                raise TeacherDecisionChannelError(
                    "connection epoch changed while minting teacher authorization"
                )
            if (
                type(receipt) is not TeacherRunAuthorization
                or receipt.binding != binding
                or receipt.active is not True
            ):
                if type(receipt) is TeacherRunAuthorization:
                    try:
                        authorizer.close_run(
                            receipt,
                            "invalid teacher authorization receipt",
                        )
                    except TeacherRunAuthorizationError:
                        receipt.invalidate("invalid teacher authorization receipt")
                raise TeacherDecisionChannelError(
                    "teacher authorization receipt does not match the approved run"
                )

            self._finish("teacher decision consumed")
            return receipt
        except Exception as exc:
            if receipt is not None and receipt.active:
                try:
                    authorizer.close_run(receipt, "teacher decision failed closed")
                except TeacherRunAuthorizationError:
                    receipt.invalidate("teacher decision failed closed")
            with self._lock:
                already_terminal = self._terminal
            if not already_terminal:
                self._finish(exc)
            if isinstance(exc, TeacherDecisionChannelError):
                raise
            if isinstance(exc, TeacherRunAuthorizationError):
                raise TeacherDecisionChannelError(str(exc)) from exc
            raise TeacherDecisionChannelError(
                "teacher decision failed closed"
            ) from exc
