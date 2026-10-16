# Third-party notices

The classroom archive contains the following pinned third-party material:

- Blockly 13.2.1, Apache-2.0, prepared from the exact npm lock file;
- `RobotWindow.js` and `request_methods.js` from Webots R2025a commit
  `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`, Apache-2.0;
- `Crazyflie.proto`, its two COLLADA meshes and `fast_helix.png` from the same
  Webots commit. The PROTO retains Cyberbotics’ Webots asset-license header and
  is distributed only for use with Webots.

Webots is an explicit prerequisite and is not redistributed in this archive.
The project’s `LICENSE` and upstream notices remain authoritative.

## Default Webots floor appearance

The four `worlds/textures/parquetry/chequered_parquetry_*.jpg` maps are copied
unchanged from the pinned Webots R2025a source used for this package. They restore
the default `Floor` appearance (`Parquetry { type "chequered" }`) with the same
0.50 m texture repeat. The existing classroom floor collision box is retained.

Source: `projects/appearances/protos/textures/parquetry/` in
https://github.com/cyberbotics/webots/tree/R2025a.
Copyright Cyberbotics Ltd.; Webots assets license:
https://cyberbotics.com/webots_assets_license.
