#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def load_netlog(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data.get("events"), list):
        raise AssertionError("NetLog has no events list")
    constants = data.get("constants", {})
    event_types = constants.get("logEventTypes", {})
    phases = constants.get("logEventPhase", {})
    if "URL_REQUEST_START_JOB" not in event_types:
        raise AssertionError("NetLog constants missing URL_REQUEST_START_JOB")
    if "PHASE_BEGIN" not in phases or "PHASE_END" not in phases:
        raise AssertionError("NetLog constants missing begin/end phases")
    return data


def external_requests(data):
    request_type = data["constants"]["logEventTypes"]["URL_REQUEST_START_JOB"]
    begin_phase = data["constants"]["logEventPhase"]["PHASE_BEGIN"]
    end_phase = data["constants"]["logEventPhase"]["PHASE_END"]
    requests = {}

    for event in data["events"]:
        if event.get("type") != request_type:
            continue
        source_id = event.get("source", {}).get("id")
        if source_id is None:
            continue

        if event.get("phase") == begin_phase:
            url = event.get("params", {}).get("url")
            if not isinstance(url, str):
                continue
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or parsed.hostname in LOOPBACK_HOSTS:
                continue
            requests[source_id] = {"url": url, "end": None}
        elif event.get("phase") == end_phase and source_id in requests:
            requests[source_id]["end"] = event.get("params", {})

    return list(requests.values())


def classify(requests):
    failed = []
    successful = []
    unresolved = []
    for request in requests:
        end = request["end"]
        if end is None:
            unresolved.append(request)
            continue
        net_error = end.get("net_error")
        if isinstance(net_error, int) and net_error < 0:
            failed.append(request)
        else:
            successful.append(request)
    return failed, successful, unresolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("netlog")
    parser.add_argument("--expect-blocked-url")
    args = parser.parse_args()

    data = load_netlog(args.netlog)
    failed, successful, unresolved = classify(external_requests(data))

    if successful:
        urls = sorted({request["url"] for request in successful})
        raise AssertionError(
            "external HTTP(S) request completed without a failing net_error: " + ", ".join(urls)
        )
    if unresolved:
        urls = sorted({request["url"] for request in unresolved})
        raise AssertionError(
            "external HTTP(S) request remained unresolved when Chrome stopped: " + ", ".join(urls)
        )

    if args.expect_blocked_url:
        if not any(request["url"] == args.expect_blocked_url for request in failed):
            raise AssertionError(
                "expected blocked required URL was not observed as a failed request: "
                + args.expect_blocked_url
            )
        print(f"NETLOG_REQUIRED_EXTERNAL_BLOCKED=PASS url={args.expect_blocked_url}")
    else:
        print(f"NETLOG_RUNTIME_OFFLINE=PASS blocked_external_attempts={len(failed)}")


if __name__ == "__main__":
    main()
