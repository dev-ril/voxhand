/**
 * VOXHAND Prototype - Frontend Application Engine
 * -----------------------------------------------
 * Handles:
 *  - WebSocket telemetry streaming & auto-reconnect
 *  - Real-time SVG biomechanical hand flexion animation
 *  - 6-DOF IMU pitch/roll artificial horizon visualization
 *  - Machine learning inference result rendering
 *  - Web Speech API Text-to-Speech (TTS) vocalization
 *  - Low-confidence auditory alert tones via Web Audio API
 *  - Interactive simulation triggers and manual overrides
 */

(function () {
  "use strict";

  // --- Configuration & State ---
  const DEFAULT_WS_PORT = 8000;
  const CONFIDENCE_THRESHOLD = 0.70;
  
  let ws = null;
  let isConnected = false;
  let ttsEnabled = true;
  let lastSpokenGesture = "";
  let lastSpokenTime = 0;
  const DEBOUNCE_SPEECH_MS = 2500; // Prevent spamming same gesture vocalization

  let frameCount = 0;
  let fps = 0;
  let fpsTimer = Date.now();

  let autoDemoInterval = null;
  let autoDemoIdx = 0;
  const DEMO_GESTURES = ["HELLO", "THANK YOU", "HELP", "YES", "NO", "REST_OR_NOISE"];

  // Web Audio Context for audible low-confidence alerts
  let audioCtx = null;

  // --- DOM Elements ---
  const wsUrlInput = document.getElementById("wsUrlInput");
  const btnConnect = document.getElementById("btnConnect");
  const connectionPill = document.getElementById("connectionPill");
  const connectionDot = document.getElementById("connectionDot");
  const connectionLabel = document.getElementById("connectionLabel");
  const fpsBadge = document.getElementById("fpsBadge");

  const btnTtsToggle = document.getElementById("btnTtsToggle");
  const ttsIcon = document.getElementById("ttsIcon");
  const ttsLabel = document.getElementById("ttsLabel");

  const translationCard = document.getElementById("translationCard");
  const translatedOutput = document.getElementById("translatedOutput");
  const statusBadge = document.getElementById("statusBadge");
  const statusText = document.getElementById("statusText");
  const speechWaveform = document.getElementById("speechWaveform");
  const nudgeAlert = document.getElementById("nudgeAlert");
  const lastConfirmedSign = document.getElementById("lastConfirmedSign");
  const lastUpdatedTimer = document.getElementById("lastUpdatedTimer");

  const confidencePercentage = document.getElementById("confidencePercentage");
  const confidenceRing = document.getElementById("confidenceRing");
  const confidenceBar = document.getElementById("confidenceBar");
  const probabilitiesList = document.getElementById("probabilitiesList");

  // Hand visualizer DOM
  const flexVals = [
    document.getElementById("valFlex0"),
    document.getElementById("valFlex1"),
    document.getElementById("valFlex2"),
    document.getElementById("valFlex3"),
    document.getElementById("valFlex4"),
  ];
  const flexBars = [
    document.getElementById("barFlex0"),
    document.getElementById("barFlex1"),
    document.getElementById("barFlex2"),
    document.getElementById("barFlex3"),
    document.getElementById("barFlex4"),
  ];

  // SVG Finger elements
  const svgThumb = document.getElementById("svgThumb");
  const svgIndex = document.getElementById("svgIndex");
  const svgMiddle = document.getElementById("svgMiddle");
  const svgRing = document.getElementById("svgRing");
  const svgPinky = document.getElementById("svgPinky");

  // IMU DOM
  const horizonPlate = document.getElementById("horizonPlate");
  const valPitch = document.getElementById("valPitch");
  const valRoll = document.getElementById("valRoll");
  const valAx = document.getElementById("valAx");
  const valAy = document.getElementById("valAy");
  const valAz = document.getElementById("valAz");
  const valGx = document.getElementById("valGx");
  const valGy = document.getElementById("valGy");
  const valGz = document.getElementById("valGz");

  // History & Simulator DOM
  const historyContainer = document.getElementById("historyContainer");
  const btnClearHistory = document.getElementById("btnClearHistory");
  const btnAutoDemo = document.getElementById("btnAutoDemo");
  const autoDemoLabel = document.getElementById("autoDemoLabel");

  // Manual sliders
  const sliderManualFlex = document.getElementById("sliderManualFlex");
  const sliderFlexVal = document.getElementById("sliderFlexVal");
  const sliderManualAccel = document.getElementById("sliderManualAccel");
  const sliderAccelVal = document.getElementById("sliderAccelVal");
  const btnEmitManual = document.getElementById("btnEmitManual");

  // --- Initial Setup ---
  function getInitialWsUrl() {
    if (window.location.protocol === "http:" || window.location.protocol === "https:") {
      const host = window.location.hostname || "localhost";
      const port = window.location.port || DEFAULT_WS_PORT;
      return `ws://${host}:${port}/ws/stream`;
    }
    return `ws://localhost:${DEFAULT_WS_PORT}/ws/stream`;
  }

  wsUrlInput.value = getInitialWsUrl();

  // --- Audio Notification Synthesizer (Web Audio API) ---
  function playAudibleNudge() {
    try {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioCtx.state === "suspended") {
        audioCtx.resume();
      }

      // Generate a pleasant warning double-pip (380Hz then 300Hz)
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(380, audioCtx.currentTime);
      osc.frequency.setValueAtTime(290, audioCtx.currentTime + 0.12);

      gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.35);

      osc.connect(gain);
      gain.connect(audioCtx.destination);

      osc.start();
      osc.stop(audioCtx.currentTime + 0.35);
    } catch (e) {
      console.warn("Audio Context playback prevented:", e);
    }
  }

  // --- Web Speech API TTS Vocalization ---
  function speakWord(text) {
    if (!ttsEnabled || !window.speechSynthesis) return;

    window.speechSynthesis.cancel(); // Stop any pending speech

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.05;
    utterance.lang = "en-US";

    // Show animated sound wave while speech is active
    speechWaveform.classList.remove("hidden");
    speechWaveform.classList.add("flex");

    utterance.onend = () => {
      speechWaveform.classList.add("hidden");
      speechWaveform.classList.remove("flex");
    };

    utterance.onerror = () => {
      speechWaveform.classList.add("hidden");
      speechWaveform.classList.remove("flex");
    };

    window.speechSynthesis.speak(utterance);
  }

  // --- WebSocket Stream Management ---
  function connectWebSocket(url) {
    if (ws) {
      try {
        ws.close();
      } catch (e) {}
    }

    updateConnectionUI("CONNECTING");

    try {
      ws = new WebSocket(url);
    } catch (err) {
      console.error("[WS] Initialization error:", err);
      updateConnectionUI("OFFLINE");
      return;
    }

    ws.onopen = () => {
      console.log("[WS] Connected to:", url);
      isConnected = true;
      updateConnectionUI("CONNECTED");
    };

    ws.onmessage = (event) => {
      handleIncomingPacket(event.data);
    };

    ws.onclose = () => {
      isConnected = false;
      updateConnectionUI("OFFLINE");
    };

    ws.onerror = (err) => {
      console.warn("[WS] Error:", err);
      isConnected = false;
      updateConnectionUI("OFFLINE");
    };
  }

  function updateConnectionUI(state) {
    if (state === "CONNECTED") {
      connectionPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/10 border border-emerald-500/30 text-emerald-400";
      connectionDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-pulse";
      connectionLabel.textContent = "Live Stream Connected";
      fpsBadge.classList.remove("hidden");
    } else if (state === "CONNECTING") {
      connectionPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/10 border border-amber-500/30 text-amber-400";
      connectionDot.className = "w-2 h-2 rounded-full bg-amber-400 animate-pulse";
      connectionLabel.textContent = "Connecting...";
      fpsBadge.classList.add("hidden");
    } else {
      connectionPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 border border-red-500/30 text-red-400";
      connectionDot.className = "w-2 h-2 rounded-full bg-red-500";
      connectionLabel.textContent = "Disconnected";
      fpsBadge.classList.add("hidden");
    }
  }

  // --- Packet Ingestion & Processing ---
  function handleIncomingPacket(rawMessage) {
    let data;
    try {
      data = JSON.parse(rawMessage);
    } catch (e) {
      return;
    }

    // Measure FPS
    frameCount++;
    const now = Date.now();
    if (now - fpsTimer >= 1000) {
      fps = frameCount;
      frameCount = 0;
      fpsTimer = now;
      fpsBadge.textContent = `${fps} FPS`;
    }

    // Packet type A: Standard INFERENCE_RESULT broadcasted from FastAPI gateway
    if (data.type === "INFERENCE_RESULT" || data.predicted_label) {
      renderInferenceResult(data);
      if (data.raw_sensor) {
        renderSensorTelemetry(data.raw_sensor);
      }
    }
    // Packet type B: Direct raw sensor packet from mock streamer (port 8080 or client)
    else if (data.flex) {
      renderSensorTelemetry(data);
      // Run local client-side prediction preview if not already wrapped
      if (!data.predicted_label) {
        requestBackendPrediction(data);
      }
    }
  }

  // Fallback REST caller if connected to mock 8080 directly without gateway inference
  async function requestBackendPrediction(sensorData) {
    try {
      const res = await fetch("http://localhost:8000/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sensorData),
      });
      if (res.ok) {
        const inf = await res.json();
        renderInferenceResult(inf);
      }
    } catch (e) {
      // Gateway offline or running standalone
    }
  }

  // --- Render ML Inference & Speech Logic ---
  function renderInferenceResult(inf) {
    const isRejected = inf.is_rejected || (inf.confidence < CONFIDENCE_THRESHOLD) || (inf.status === "REJECTED");
    const confidencePct = Math.round((inf.confidence || 0) * 100);
    const displayText = inf.text || inf.predicted_label || "--";

    // Update Output Text
    translatedOutput.textContent = displayText;

    // Update Status Pill
    if (isRejected) {
      statusBadge.className = "flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/30";
      statusText.textContent = "REJECTED (LOW CONFIDENCE)";
      nudgeAlert.classList.remove("hidden");
      translationCard.classList.add("alert-nudge");
      translationCard.classList.remove("glow-emerald");

      // Audible alert on rejection
      const now = Date.now();
      if (now - lastSpokenTime > 3000) {
        playAudibleNudge();
        lastSpokenTime = now;
      }
    } else {
      statusBadge.className = "flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
      statusText.textContent = "CONFIRMED ACCURATE";
      nudgeAlert.classList.add("hidden");
      translationCard.classList.remove("alert-nudge");
      translationCard.classList.add("glow-emerald");

      lastConfirmedSign.textContent = displayText;

      // Vocalize gesture if confirmed and debounced
      const now = Date.now();
      if (displayText !== lastSpokenGesture || (now - lastSpokenTime >= DEBOUNCE_SPEECH_MS)) {
        speakWord(displayText);
        lastSpokenGesture = displayText;
        lastSpokenTime = now;
        addHistoryItem(displayText, confidencePct, true);
      }
    }

    lastUpdatedTimer.textContent = `Updated: ${new Date().toLocaleTimeString()}`;

    // Update Radial Confidence Meter
    confidencePercentage.textContent = `${confidencePct}%`;
    const circumference = 2 * Math.PI * 42; // r=42 -> ~264
    const offset = circumference - (confidencePct / 100) * circumference;
    confidenceRing.style.strokeDashoffset = offset;

    // Adjust ring color
    if (isRejected) {
      confidenceRing.setAttribute("class", "text-amber-500 transition-all duration-300");
      confidenceBar.className = "bg-amber-500 h-2.5 rounded-full transition-all duration-200";
    } else {
      confidenceRing.setAttribute("class", "text-emerald-400 transition-all duration-300");
      confidenceBar.className = "bg-emerald-500 h-2.5 rounded-full transition-all duration-200";
    }
    confidenceBar.style.width = `${Math.min(100, Math.max(0, confidencePct))}%`;

    // Render Probabilities breakdown
    if (inf.probabilities) {
      renderProbabilities(inf.probabilities, inf.predicted_label);
    }
  }

  function renderProbabilities(probs, activeLabel) {
    probabilitiesList.innerHTML = "";
    Object.entries(probs).forEach(([clsName, pVal]) => {
      const pct = Math.round(pVal * 100);
      const isTarget = clsName === activeLabel;
      const row = document.createElement("div");
      row.className = `flex items-center justify-between p-1 rounded ${isTarget ? "bg-teal-900/30 text-teal-300 font-bold" : "text-gray-400"}`;
      row.innerHTML = `
        <span class="truncate w-28 text-[11px]">${clsName}</span>
        <div class="w-24 bg-gray-800 rounded-full h-1.5 overflow-hidden mx-2">
          <div class="${isTarget ? 'bg-teal-400' : 'bg-gray-600'} h-1.5 rounded-full" style="width: ${pct}%"></div>
        </div>
        <span class="w-8 text-right text-[10px]">${pct}%</span>
      `;
      probabilitiesList.appendChild(row);
    });
  }

  // --- Render Physical Sensor Telemetry (Hand & IMU) ---
  function renderSensorTelemetry(sensor) {
    const flex = sensor.flex || [0, 0, 0, 0, 0];
    const accel = sensor.accel || { x: 0, y: 0.98, z: 0.15 };
    const gyro = sensor.gyro || { x: 0, y: 0, z: 0 };

    // Update 5 Flex Bars & Labels
    flex.forEach((val, i) => {
      if (i < 5) {
        const pct = Math.round(val * 100);
        flexVals[i].textContent = `${val.toFixed(2)} (${pct}%)`;
        flexBars[i].style.width = `${pct}%`;
        
        // Color transition as flex increases
        if (pct > 70) {
          flexBars[i].className = "bg-rose-500 h-2 rounded-full transition-all duration-100";
        } else if (pct > 40) {
          flexBars[i].className = "bg-amber-400 h-2 rounded-full transition-all duration-100";
        } else {
          flexBars[i].className = "bg-teal-500 h-2 rounded-full transition-all duration-100";
        }
      }
    });

    // Update Biomechanical SVG Hand Model
    updateSvgHandBones(flex);

    // Update IMU Attitude & Accelerometer/Gyro
    const ax = Number(accel.x || 0);
    const ay = Number(accel.y || 0);
    const az = Number(accel.z || 0);

    const gx = Number(gyro.x || 0);
    const gy = Number(gyro.y || 0);
    const gz = Number(gyro.z || 0);

    valAx.textContent = `${ax >= 0 ? "+" : ""}${ax.toFixed(2)}g`;
    valAy.textContent = `${ay >= 0 ? "+" : ""}${ay.toFixed(2)}g`;
    valAz.textContent = `${az >= 0 ? "+" : ""}${az.toFixed(2)}g`;

    valGx.textContent = `${gx.toFixed(2)}`;
    valGy.textContent = `${gy.toFixed(2)}`;
    valGz.textContent = `${gz.toFixed(2)}`;

    // Compute Pitch & Roll in degrees from accelerometer
    // Pitch = atan2(ay, sqrt(ax^2 + az^2))
    // Roll  = atan2(-ax, az)
    const pitchRad = Math.atan2(ay, Math.sqrt(ax * ax + az * az));
    const rollRad = Math.atan2(-ax, az);
    const pitchDeg = Math.round(pitchRad * (180 / Math.PI));
    const rollDeg = Math.round(rollRad * (180 / Math.PI));

    valPitch.textContent = `${pitchDeg}°`;
    valRoll.textContent = `${rollDeg}°`;

    // Translate artificial horizon disc
    const offsetY = Math.min(30, Math.max(-30, pitchDeg * 0.6));
    horizonPlate.style.transform = `rotate(${rollDeg}deg) translateY(${offsetY}px)`;
  }

  // Animate SVG hand bones based on 0.0 - 1.0 flexion
  function updateSvgHandBones(flex) {
    const bones = [svgThumb, svgIndex, svgMiddle, svgRing, svgPinky];
    const fingerLines = [
      { bone: svgThumb,  x1: 65,  y1: 165, x2: 35,  y2: 135, originX: 65,  originY: 165 },
      { bone: svgIndex,  x1: 85,  y1: 160, x2: 85,  y2: 65,  originX: 85,  originY: 160 },
      { bone: svgMiddle, x1: 120, y1: 158, x2: 120, y2: 45,  originX: 120, originY: 158 },
      { bone: svgRing,   x1: 155, y1: 160, x2: 155, y2: 65,  originX: 155, originY: 160 },
      { bone: svgPinky,  x1: 180, y1: 168, x2: 195, y2: 90,  originX: 180, originY: 168 },
    ];

    fingerLines.forEach((item, idx) => {
      const fVal = flex[idx] || 0;
      // As finger bends, scale down along Y axis and rotate inward slightly
      const scaleY = 1.0 - (fVal * 0.55); // Shrinks down to simulate curl
      const line = item.bone.querySelector("line");
      const circle = item.bone.querySelector("circle");

      if (line && circle) {
        // Adjust color based on strain
        const strokeColor = fVal > 0.7 ? "#f43f5e" : fVal > 0.35 ? "#f59e0b" : "#14b8a6";
        line.setAttribute("stroke", strokeColor);
        circle.setAttribute("fill", strokeColor);

        // Apply SVG transform relative to base joint
        item.bone.style.transformOrigin = `${item.originX}px ${item.originY}px`;
        item.bone.style.transform = `scaleY(${scaleY})`;
      }
    });
  }

  // --- Speech & Event History Log ---
  function addHistoryItem(text, confidencePct, isConfirmed) {
    // Remove empty placeholder
    const placeholder = historyContainer.querySelector("p");
    if (placeholder) placeholder.remove();

    const item = document.createElement("div");
    item.className = "flex items-center justify-between p-2.5 rounded-xl bg-gray-900/90 border border-gray-800 transition hover:border-gray-700";
    
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    item.innerHTML = `
      <div class="flex items-center space-x-2">
        <span class="w-1.5 h-1.5 rounded-full ${isConfirmed ? 'bg-teal-400' : 'bg-amber-400'}"></span>
        <strong class="text-white text-xs">${text}</strong>
        <span class="text-[10px] text-gray-500 font-mono">${timeStr}</span>
      </div>
      <div class="flex items-center space-x-2">
        <span class="text-[10px] font-mono ${isConfirmed ? 'text-teal-400' : 'text-amber-400'}">${confidencePct}%</span>
        <button class="btn-replay p-1 text-gray-400 hover:text-teal-400 transition" title="Speak word">
          <i data-lucide="volume-2" class="w-3.5 h-3.5"></i>
        </button>
      </div>
    `;

    item.querySelector(".btn-replay").addEventListener("click", () => {
      speakWord(text);
    });

    historyContainer.prepend(item);
    lucide.createIcons();

    // Limit log size to 20
    if (historyContainer.children.length > 20) {
      historyContainer.lastElementChild.remove();
    }
  }

  // --- Interactive Simulation Lab Triggers ---
  function triggerSimulation(gestureName) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "SIMULATE_COMMAND",
        gesture: gestureName
      }));
    } else {
      // Fallback via HTTP POST
      fetch("http://localhost:8000/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gesture: gestureName })
      })
      .then(res => res.json())
      .then(data => {
        if (data.inference) renderInferenceResult(data.inference);
        if (data.simulation) renderSensorTelemetry(data.simulation);
      })
      .catch(err => console.error("Simulate fetch error:", err));
    }
  }

  // --- Event Listeners ---
  btnConnect.addEventListener("click", () => {
    const url = wsUrlInput.value.trim();
    if (url) connectWebSocket(url);
  });

  btnTtsToggle.addEventListener("click", () => {
    ttsEnabled = !ttsEnabled;
    if (ttsEnabled) {
      ttsLabel.textContent = "TTS Active";
      btnTtsToggle.className = "flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-teal-500/15 border border-teal-500/40 text-teal-300 hover:bg-teal-500/25 transition";
      ttsIcon.setAttribute("data-lucide", "volume-2");
    } else {
      ttsLabel.textContent = "TTS Muted";
      btnTtsToggle.className = "flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 border border-gray-700 text-gray-400 hover:bg-gray-700 transition";
      ttsIcon.setAttribute("data-lucide", "volume-x");
      window.speechSynthesis.cancel();
    }
    lucide.createIcons();
  });

  btnClearHistory.addEventListener("click", () => {
    historyContainer.innerHTML = '<p class="text-gray-600 italic text-center py-6">No speech events logged yet.</p>';
  });

  // Simulator buttons
  document.querySelectorAll(".btn-gesture").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const gesture = btn.getAttribute("data-sim");
      triggerSimulation(gesture);
    });
  });

  // Auto-Cycle Demo Mode
  btnAutoDemo.addEventListener("click", () => {
    if (autoDemoInterval) {
      clearInterval(autoDemoInterval);
      autoDemoInterval = null;
      autoDemoLabel.textContent = "Start Auto-Cycle Demo";
      btnAutoDemo.className = "px-3 py-1 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/40 text-purple-300 rounded-lg text-xs font-medium transition flex items-center space-x-1.5";
    } else {
      autoDemoLabel.textContent = "Stop Auto-Cycle Demo";
      btnAutoDemo.className = "px-3 py-1 bg-red-600/20 hover:bg-red-600/30 border border-red-500/40 text-red-300 rounded-lg text-xs font-medium transition flex items-center space-x-1.5";
      
      // Immediately run first
      triggerSimulation(DEMO_GESTURES[autoDemoIdx]);
      autoDemoInterval = setInterval(() => {
        autoDemoIdx = (autoDemoIdx + 1) % DEMO_GESTURES.length;
        triggerSimulation(DEMO_GESTURES[autoDemoIdx]);
      }, 3500);
    }
  });

  // Manual Sliders
  sliderManualFlex.addEventListener("input", (e) => {
    sliderFlexVal.textContent = parseFloat(e.target.value).toFixed(2);
  });

  sliderManualAccel.addEventListener("input", (e) => {
    sliderAccelVal.textContent = `${parseFloat(e.target.value).toFixed(2)}g`;
  });

  btnEmitManual.addEventListener("click", () => {
    const fVal = parseFloat(sliderManualFlex.value);
    const aVal = parseFloat(sliderManualAccel.value);
    const manualFrame = {
      flex: [fVal, fVal, fVal, fVal, fVal],
      accel: { x: 0.05, y: aVal, z: 0.2 },
      gyro: { x: 0.0, y: 0.0, z: 0.0 },
      timestamp: Math.floor(Date.now() / 1000)
    };

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(manualFrame));
    } else {
      fetch("http://localhost:8000/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(manualFrame)
      })
      .then(res => res.json())
      .then(inf => {
        renderInferenceResult(inf);
        renderSensorTelemetry(manualFrame);
      });
    }
  });

  // Auto-connect on load
  connectWebSocket(wsUrlInput.value);

  // Background auto-reconnect timer if disconnected
  setInterval(() => {
    if (!isConnected && (!ws || ws.readyState === WebSocket.CLOSED)) {
      const url = wsUrlInput.value.trim();
      if (url) connectWebSocket(url);
    }
  }, 4000);

})();

