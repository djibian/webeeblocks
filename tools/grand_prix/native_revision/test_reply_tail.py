"""Static source-order regressions for experimental Webots revision responses.

This does not simulate a native Webots reply, prove wire integrity, qualify the
guarded effect, or allow production authority. The Draft still requires native
malformed-reply injection and independent review.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
PATCH = ROOT / "webots-r2025a-revision.patch"


def section(source, file):
    marker = f"diff --git a/{file} b/{file}"
    return source.split(marker, 1)[1].split("diff --git ", 1)[0]


class RevisionTrailerContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch = PATCH.read_text(encoding="utf-8")

    def test_experimental_answers_follow_ordinary_robot_answers(self):
        controller = section(self.patch, "src/webots/control/WbController.cpp")
        ordered = [
            "mRobot->dispatchAnswer(stream);",
            "mRobot->writeImmediateAnswer(stream);",
            "mRobot->supervisorUtilities()->writeSceneRevisionAnswer(stream);",
        ]
        indices = [controller.index(part) for part in ordered]
        self.assertEqual(indices, sorted(indices))
        writer = section(self.patch, "src/webots/nodes/utils/WbSupervisorUtilities.cpp")
        self.assertIn("+bool WbSupervisorUtilities::writeSceneRevisionAnswer(", writer)
        ordinary = writer.split(" void WbSupervisorUtilities::writeAnswer(WbDataStream &stream) {", 1)[1]
        self.assertNotIn("if (mSendSceneRevision)", ordinary)

    def test_revision_reply_is_exclusive_of_frame_104(self):
        controller = section(self.patch, "src/webots/control/WbController.cpp")
        writer = section(self.patch, "src/webots/nodes/utils/WbSupervisorUtilities.cpp")
        self.assertIn("const bool revisionReplyConsumed", controller)
        self.assertIn("if (revisionReplyConsumed)", controller)
        self.assertIn("mRobot->supervisorUtilities()->invalidatePhysicsFrame();", controller)
        self.assertLess(controller.index("writeSceneRevisionAnswer(stream)"),
                        controller.index("writePhysicsFrame(stream"))
        self.assertIn("if (mSendSceneRevision && mRevisionEffectResult >= 0)", writer)
        self.assertIn("mRevisionEffectResult = -1;", writer)
        self.assertIn("+  return true;", writer)

    def test_revision_token_requires_exact_terminal_length(self):
        reader = section(self.patch, "src/controller/c/supervisor.c")
        token = reader.split("+    case C_SUPERVISOR_GET_SCENE_REVISION: {", 1)[1].split(
            "+    case C_SUPERVISOR_SET_VELOCITY_AT_SCENE_REVISION: {", 1)[0]
        self.assertIn("!scene_revision_request", token)
        self.assertIn("end - request_get_position(r) != (int)sizeof(scene_revision_result)", token)
        self.assertIn("request_set_position(r, end);", token)

    def test_velocity_ack_requires_exclusive_one_byte_reply(self):
        reader = section(self.patch, "src/controller/c/supervisor.c")
        ack = reader.split("+    case C_SUPERVISOR_SET_VELOCITY_AT_SCENE_REVISION: {", 1)[1].split(
            " case C_SUPERVISOR_PHYSICS_FRAME:", 1)[0]
        self.assertIn("!scene_revision_expected", ack)
        self.assertIn("request_get_size(r) - request_get_position(r) != 1", ack)
        self.assertIn("request_set_position(r, request_get_size(r));", ack)
        self.assertIn("scene_revision_effect_applied = request_read_uchar(r) == 1;", ack)

    def test_joint_position_source_hook_precedes_effect(self):
        # Static source-order claim only; a colliding-joint move/restore native
        # witness and stale-token refusal remain indispensable.
        cpp = section(self.patch, "src/webots/nodes/utils/WbSupervisorUtilities.cpp")
        self.assertIn("+        WbWorld::instance()->noteSceneEffect();\\n         joint->setPosition(position, index);".replace("\\n", "\n"), cpp)



if __name__ == "__main__":
    unittest.main()
