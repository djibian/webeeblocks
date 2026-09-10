#!/usr/bin/env python3

import argparse
import csv
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie


TARGET_SHA = "173b7c5b189b4c4241d7fbde5b1443214dd20a14"
ARTIFACT = "experimental-s3-surface-offset-2026-08"
ARTIFACT_SHA256 = "e2889f56c1a6b85b0021e7b4a1e7cc99142517041696b769ece6ecdff87ec31a"
CF2_SHA256 = "0edf7053b060705b1491fa01c77e97d637b0d24376a4ea21c3bdbc03a902f076"

PARAMS_REQUIRED = [
    "stabilizer.estimator",
    "ukf.resetEstimation",
    "ukf.qualityGateTof",
    "ukf.baroNoise",
    "ukf.surfaceOffsetS3",
]

LOG_BLOCKS = {
    "state": [
        "stateEstimate.x",
        "stateEstimate.y",
        "stateEstimate.z",
        "stateEstimate.vx",
        "stateEstimate.vy",
        "stateEstimate.vz",
    ],
    "filter": [
        "sensorFilter.distPred",
        "sensorFilter.distMeas",
        "sensorFilter.baroHeight",
        "sensorFilter.innoChFlow_x",
        "sensorFilter.innoChFlow_y",
        "sensorFilter.innoChTof",
    ],
    "motion_a": [
        "motion.deltaX",
        "motion.deltaY",
        "motion.shutter",
        "motion.squal",
    ],
    "motion_b": [
        "motion.outlierCount",
        "motion.motion",
        "motion.std",
    ],
    "surface_a": [
        "sensorFilter.flowRange",
        "sensorFilter.flowLocal",
        "sensorFilter.surfOffset",
        "sensorFilter.surfCand",
        "sensorFilter.surfClear",
    ],
    "surface_b": [
        "sensorFilter.surfBefore",
        "sensorFilter.surfAfter",
        "sensorFilter.surfDelta",
        "sensorFilter.surfSign",
    ],
    "surface_c": [
        "sensorFilter.surfN",
        "sensorFilter.surfBaroD",
        "sensorFilter.surfCandInn",
        "sensorFilter.surfState",
        "sensorFilter.surfReason",
    ],
    "range_attitude": [
        "range.zrange",
        "stabilizer.roll",
        "stabilizer.pitch",
    ],
}

logging.basicConfig(level=logging.ERROR)

lock = threading.Lock()
current_phase = None
writers = {}
files = {}
latest_cf_timestamp = None
log_errors = []


def toc_has(toc, complete_name):
    group, name = complete_name.split(".", 1)
    return group in toc and name in toc[group]


def set_param_and_wait(cf, name, value):
    group, short_name = name.split(".", 1)

    event = threading.Event()
    result = {}

    def callback(param_name, param_value):
        result["name"] = param_name
        result["value"] = param_value
        event.set()

    cf.param.add_update_callback(
        group=group,
        name=short_name,
        cb=callback,
    )

    event.clear()
    cf.param.set_value(name, str(value))

    if not event.wait(timeout=3.0):
        raise RuntimeError(f"Pas d'accusé de réception pour {name}")

    print(f"  {name} = {result['value']}")
    return result["value"]


def get_param(cf, name):
    return cf.param.get_value(name)


def make_callback(block_name, variables):
    def callback(timestamp, data, logconf):
        global latest_cf_timestamp

        with lock:
            latest_cf_timestamp = timestamp

            if current_phase is None:
                return

            writer = writers.get(block_name)
            if writer is None:
                return

            row = {
                "cf_timestamp_ms": timestamp,
                "host_monotonic_s": f"{time.monotonic():.6f}",
            }

            for variable in variables:
                row[variable] = data.get(variable, "")

            writer.writerow(row)

    return callback


def log_error(logconf, msg):
    message = f"{logconf.name}: {msg}"
    log_errors.append(message)
    print(f"\nERREUR LOG: {message}", file=sys.stderr)


def open_phase(output_root, phase):
    global current_phase, writers, files

    phase_dir = output_root / phase
    phase_dir.mkdir(parents=True, exist_ok=True)

    with lock:
        writers = {}
        files = {}

        for block_name, variables in LOG_BLOCKS.items():
            path = phase_dir / f"{block_name}.csv"
            f = path.open("w", newline="", encoding="utf-8")
            files[block_name] = f

            fieldnames = [
                "cf_timestamp_ms",
                "host_monotonic_s",
                *variables,
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writers[block_name] = writer

        marker_file = (phase_dir / "markers.csv").open(
            "w", newline="", encoding="utf-8"
        )
        files["_markers"] = marker_file

        marker_writer = csv.DictWriter(
            marker_file,
            fieldnames=[
                "event",
                "cf_timestamp_ms_nearest",
                "host_monotonic_s",
            ],
        )
        marker_writer.writeheader()
        writers["_markers"] = marker_writer

        current_phase = phase


def marker(event):
    with lock:
        writer = writers.get("_markers")
        if writer:
            writer.writerow({
                "event": event,
                "cf_timestamp_ms_nearest": latest_cf_timestamp,
                "host_monotonic_s": f"{time.monotonic():.6f}",
            })
            files["_markers"].flush()


def close_phase():
    global current_phase, writers, files

    with lock:
        current_phase = None

        for f in files.values():
            f.flush()
            f.close()

        writers = {}
        files = {}


def capture_manual(output_root, phase, instructions):
    print("\n" + "=" * 72)
    print(phase)
    print("=" * 72)
    print(instructions)
    print()

    input("ENTER quand tu es prêt à COMMENCER cette séquence... ")

    open_phase(output_root, phase)
    marker("START")

    print("\nENREGISTREMENT EN COURS.")
    input("Effectue maintenant toute la séquence puis appuie sur ENTER à la FIN... ")

    marker("END")
    close_phase()

    print(f"Enregistrement {phase} terminé.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--uri",
        default=os.environ.get(
            "CFLIB_URI",
            "radio://0/80/2M/E7E7E7E7E7",
        ),
    )
    parser.add_argument(
        "--period",
        type=int,
        choices=[20, 50],
        default=20,
    )
    parser.add_argument(
        "--output",
        default="results",
    )
    args = parser.parse_args()

    uri = args.uri
    period = args.period
    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("WEBEEBLOCKS S3 PROPS-OFF CHECKPOINT #180")
    print("=" * 72)
    print(f"URI             : {uri}")
    print(f"Target SHA      : {TARGET_SHA}")
    print(f"Logging period  : {period} ms")
    print()
    print("ATTENTION : LES 4 HELICES DOIVENT ETRE RETIREES.")
    print("Ce programme n'envoie aucune commande moteur.")
    print()

    answer = input("Tape exactement OUI pour confirmer hélices retirées : ")
    if answer != "OUI":
        print("Abandon.")
        sys.exit(1)

    cflib.crtp.init_drivers()

    cache = output_root / "cache"
    cache.mkdir(exist_ok=True)

    cf = Crazyflie(rw_cache=str(cache))

    print("\nConnexion...")

    with SyncCrazyflie(uri, cf=cf) as scf:
        cf = scf.cf
        print("Connecté.")

        # -------- Vérification paramètres --------

        missing_params = [
            p for p in PARAMS_REQUIRED
            if not toc_has(cf.param.toc.toc, p)
        ]

        if missing_params:
            print("\nPARAMETRES S3 MANQUANTS :")
            for p in missing_params:
                print(" -", p)
            print("\nFirmware S3 attendu non confirmé. ABANDON.")
            sys.exit(2)

        # Flow Deck V2
        if toc_has(cf.param.toc.toc, "deck.bcFlow2"):
            flow = cf.param.get_value("deck.bcFlow2")
            print(f"\ndeck.bcFlow2 = {flow}")
            if int(float(flow)) != 1:
                print("Flow Deck V2 non détecté. ABANDON.")
                sys.exit(3)
        else:
            print("\nParamètre deck.bcFlow2 absent. ABANDON.")
            sys.exit(3)

        # -------- Vérification variables de log --------

        all_required_logs = [
            variable
            for variables in LOG_BLOCKS.values()
            for variable in variables
        ]

        missing_logs = [
            variable
            for variable in all_required_logs
            if not toc_has(cf.log.toc.toc, variable)
        ]

        if missing_logs:
            print("\nVARIABLES DE LOG MANQUANTES :")
            for variable in missing_logs:
                print(" -", variable)
            print("\nOracle #180 non observable. ABANDON.")
            sys.exit(4)

        print("\nToutes les variables requises sont présentes.")

        # -------- Configuration UKF exacte --------

        print("\nPose maintenant le Crazyflie à plat et parfaitement immobile.")
        input("ENTER quand il est prêt... ")

        print("\nSélection UKF :")
        set_param_and_wait(cf, "stabilizer.estimator", 3)

        print("\nReset UKF :")
        set_param_and_wait(cf, "ukf.resetEstimation", 1)
        time.sleep(0.25)
        set_param_and_wait(cf, "ukf.resetEstimation", 0)

        print("\nNE TOUCHE PAS AU CRAZYFLIE pendant 5 secondes...")
        for remaining in range(5, 0, -1):
            print(f"{remaining}...")
            time.sleep(1.0)

        print("\nParamètres S3 pré-enregistrés :")
        set_param_and_wait(cf, "ukf.qualityGateTof", 20)
        set_param_and_wait(cf, "ukf.baroNoise", 6.25)
        set_param_and_wait(cf, "ukf.surfaceOffsetS3", 1)

        time.sleep(0.5)

        configured = {
            "stabilizer.estimator":
                get_param(cf, "stabilizer.estimator"),
            "ukf.qualityGateTof":
                get_param(cf, "ukf.qualityGateTof"),
            "ukf.baroNoise":
                get_param(cf, "ukf.baroNoise"),
            "ukf.surfaceOffsetS3":
                get_param(cf, "ukf.surfaceOffsetS3"),
        }

        print("\nLecture finale paramètres :")
        for name, value in configured.items():
            print(f"  {name} = {value}")

        # -------- Métadonnées --------

        metadata = {
            "target_sha": TARGET_SHA,
            "artifact": ARTIFACT,
            "artifact_sha256": ARTIFACT_SHA256,
            "cf2_bin_sha256": CF2_SHA256,
            "uri": uri,
            "logging_period_ms": period,
            "crazyflie": "Crazyflie 2.1",
            "deck": "Flow Deck V2",
            "parameters": configured,
            "props_removed": True,
            "host_time_unix": time.time(),
        }

        with (output_root / "metadata.json").open(
            "w", encoding="utf-8"
        ) as f:
            json.dump(metadata, f, indent=2)

        # -------- Création blocs de log --------

        log_configs = []

        print("\nCréation des blocs de log...")

        for block_name, variables in LOG_BLOCKS.items():
            lg = LogConfig(
                name=block_name,
                period_in_ms=period,
            )

            for variable in variables:
                # Aucun type forcé :
                # cflib utilise le type TOC natif.
                lg.add_variable(variable)

            try:
                cf.log.add_config(lg)
            except Exception as exc:
                print(
                    f"\nImpossible de créer {block_name}: {exc}",
                    file=sys.stderr,
                )
                sys.exit(5)

            if not lg.valid:
                print(
                    f"\nBloc invalide : {block_name}",
                    file=sys.stderr,
                )
                sys.exit(5)

            lg.data_received_cb.add_callback(
                make_callback(block_name, variables)
            )
            lg.error_cb.add_callback(log_error)

            log_configs.append(lg)
            print(f"  OK {block_name}")

        for lg in log_configs:
            lg.start()

        time.sleep(2.0)

        if log_errors:
            print("\nErreur de logging avant calibration.")
            for err in log_errors:
                print(" -", err)
            print(
                "\nRelance tout le checkpoint avec --period 50."
            )
            sys.exit(6)

        # -------- CALIBRATION --------

        print("\n" + "=" * 72)
        print("CALIBRATION STATIONNAIRE")
        print("=" * 72)
        print("Sol plat uniquement.")
        print("Plateforme absente.")
        print("Crazyflie plat et parfaitement immobile.")
        input("ENTER pour démarrer 15 secondes de calibration... ")

        open_phase(output_root, "calibration")
        marker("START")

        for remaining in range(15, 0, -1):
            print(f"\rCalibration : {remaining:2d} s restantes", end="", flush=True)
            time.sleep(1.0)

        print()
        marker("END")
        close_phase()

        if log_errors:
            print("\nERREUR pendant la calibration :")
            for err in log_errors:
                print(" -", err)
            print(
                "\nN'observe PAS S3-A. "
                "Relance tout avec --period 50."
            )
            sys.exit(7)

        print("\nCalibration terminée.")
        print("NE MODIFIE PLUS AUCUN PARAMETRE.")

        # -------- S3-A --------

        capture_manual(
            output_root,
            "S3-A",
            """
TERRAIN :
- sol stable >= 4 s
- translation HORIZONTALE vers plateforme rigide ~20 cm
- maintenir la hauteur physique mondiale aussi constante que possible
- plateforme stable >= 5 s
- translation horizontale retour au sol
- sol stable >= 4 s

Ne change volontairement PAS la hauteur du Crazyflie.
""",
        )

        # -------- S3-B --------

        capture_manual(
            output_root,
            "S3-B",
            """
CONTROLE VERTICAL RAPIDE — SOL PLAT UNIQUEMENT :
- plateforme complètement retirée
- stable >= 4 s
- lever réellement le Crazyflie d'environ 20 cm
- maintenir >= 5 s
- redescendre réellement d'environ 20 cm
- maintenir >= 4 s
""",
        )

        # -------- S3-C --------

        capture_manual(
            output_root,
            "S3-C",
            """
CONTROLE VERTICAL LENT — SOL PLAT UNIQUEMENT :
- stable >= 4 s
- monter réellement d'environ 20 cm SUR 4 A 6 SECONDES
- maintenir >= 4 s
- redescendre SUR 4 A 6 SECONDES
- maintenir >= 4 s
""",
        )

        for lg in log_configs:
            lg.stop()

        if log_errors:
            print("\nATTENTION : erreurs de log enregistrées :")
            for err in log_errors:
                print(" -", err)
            print(
                "L'oracle peut être non jugeable : "
                "ne déclare pas PASS."
            )

        # Lecture finale
        final_params = {
            "stabilizer.estimator":
                get_param(cf, "stabilizer.estimator"),
            "ukf.qualityGateTof":
                get_param(cf, "ukf.qualityGateTof"),
            "ukf.baroNoise":
                get_param(cf, "ukf.baroNoise"),
            "ukf.surfaceOffsetS3":
                get_param(cf, "ukf.surfaceOffsetS3"),
        }

        with (output_root / "final_parameters.json").open(
            "w", encoding="utf-8"
        ) as f:
            json.dump(final_params, f, indent=2)

        print("\n" + "=" * 72)
        print("CAPTURE TERMINEE")
        print("=" * 72)
        print(f"Données : {output_root.resolve()}")
        print()
        print("NE FAIS AUCUN VOL.")
        print("NE RETUNE AUCUN PARAMETRE.")
        print("NE MODIFIE PAS qualityGateTof / baroNoise.")
        print("Analyse les données avant de conclure PASS ou FAIL.")


if __name__ == "__main__":
    main()
