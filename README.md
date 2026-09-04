# WebeeBlocks

WebeeBlocks is an offline-first block-programming environment for learning
algorithmic reasoning through robotics. Students build a Blockly program,
exercise it in Webots and, for the final teacher-authorized activity only, may
reuse the same backend-neutral program with a real Crazyflie.

## Product foundation

- Webots R2025a;
- Blockly 13.2.1 with the Zelos renderer;
- French student interface;
- explicit Open, Save and Save As for portable .wbb projects;
- a backend-neutral AST, preflight validation and shared interpreter;
- Webots simulation as the normal classroom execution environment;
- no student accounts, progress tracking, grading engine or automatic hints.

The durable product constraints are in docs/PRODUCT_VISION.md.

## Development

WebeeBlocks V4 uses trunk-based development:

- main is the single healthy integration trunk and default branch;
- Controller executions are stateless, interchangeable and may run in parallel
  from isolated worktrees/branches;
- Draft PRs are mutable; Ready PRs are exact frozen candidates;
- CI Gate plus an independent exact-candidate review protect integration;
- no agent lifecycle event notifies Emmanuel;
- real-world validation is rare and arrives only as one prepared TEST_REQUIRED
  checkpoint.

See docs/DEVELOPMENT.md and AGENTS.md.

## License

The project declares GPL-3.0. Bundled third-party components retain their own
license notices; a classroom release must preserve them.
