// Noor — AudioWorklet processor for low-latency mic capture
// Used when served over HTTPS (AudioWorklet requires secure context)

"use strict";

class NoorMicProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.active = true;

        this.port.onmessage = (e) => {
            if (e.data === "stop") {
                this.active = false;
            }
        };
    }

    process(inputs, outputs, parameters) {
        if (!this.active) return false;

        const input = inputs[0];
        if (input.length === 0) return true;

        const float32 = input[0];
        // Convert float32 [-1, 1] to int16 PCM
        const int16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
            const s = Math.max(-1, Math.min(1, float32[i]));
            int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        this.port.postMessage(int16.buffer, [int16.buffer]);
        return true;
    }
}

registerProcessor("noor-mic-processor", NoorMicProcessor);
