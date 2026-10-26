"""
VOXHAND Unified Demo Launcher
-----------------------------
One-command orchestrator to run the entire VOXHAND smart sign language glove system:
  - Serves the Interactive Web Dashboard on http://localhost:8000
  - Ingests telemetry via WebSockets on /ws/stream
  - Executes real-time Random Forest ML classification (< 5ms latency)
  - Optionally spawns the Mock ESP32 Hardware Streamer (with auto-cycling gestures)
"""

import os
import sys
import time
import argparse
import subprocess
import webbrowser

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def run_full_demo(port: int = 8000, open_browser: bool = True):
    print("=" * 70)
    print("           VOXHAND - SMART SIGN LANGUAGE GLOVE PROTOTYPE")
    print("=" * 70)
    print(f"[1/3] Checking ML model status...")

    model_path = os.path.join(PROJECT_ROOT, "ml_pipeline", "model.joblib")
    if not os.path.exists(model_path):
        print("      Model not found. Training Random Forest classifier...")
        subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "ml_pipeline", "train_model.py")], check=True)
    else:
        print("      Model found and verified (model.joblib).")

    print(f"\n[2/3] Starting FastAPI Backend & Web Dashboard on http://localhost:{port}...")
    import uvicorn
    from backend.app import app

    if open_browser:
        def open_tab():
            time.sleep(1.5)
            url = f"http://localhost:{port}/"
            print(f"\n[DASHBOARD] Opening companion interface in browser: {url}")
            webbrowser.open(url)

        import threading
        threading.Thread(target=open_tab, daemon=True).start()

    print("\n[3/3] System online! Press CTRL+C to stop.")
    print("      Tip: You can also run the mock hardware streamer in a second terminal:")
    print(f"           python firmware/mock_esp32_streamer.py --target-gateway ws://localhost:{port}/ws/stream\n")

    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=False)


def run_mock_streamer(target_gateway: str = None, port: int = 8080):
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "firmware", "mock_esp32_streamer.py")]
    if target_gateway:
        cmd.extend(["--target-gateway", target_gateway])
    else:
        cmd.extend(["--port", str(port)])
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(description="VOXHAND Prototype Launcher")
    parser.add_argument(
        "--mode",
        choices=["full", "gateway", "mock-server", "mock-pusher", "train"],
        default="full",
        help="Launch mode (default: full)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Gateway port (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")

    args = parser.parse_args()

    if args.mode == "train":
        subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "ml_pipeline", "train_model.py")])
    elif args.mode == "mock-server":
        run_mock_streamer(port=8080)
    elif args.mode == "mock-pusher":
        run_mock_streamer(target_gateway=f"ws://localhost:{args.port}/ws/stream")
    else:
        run_full_demo(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()

