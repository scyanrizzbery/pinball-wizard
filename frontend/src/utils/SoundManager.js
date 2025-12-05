class SoundManager {
    constructor() {
        try {
            console.log("SoundManager: Initializing...")
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
            this.masterGain = this.ctx.createGain();
            this.volume = 0.08;
            this.muted = true;
            this.masterGain.gain.value = this.volume;
            this.masterGain.connect(this.ctx.destination);
            this.enabled = true;

            // Pre-calculate distortion curve
            this.distortionCurve = this.makeDistortionCurve(400);

            console.log("SoundManager: Initialized successfully")
        } catch (e) {
            console.error("SoundManager: Initialization failed", e)
            this.enabled = false;
        }
    }

    makeDistortionCurve(amount) {
        const k = typeof amount === 'number' ? amount : 50,
            n_samples = 44100,
            curve = new Float32Array(n_samples),
            deg = Math.PI / 180;
        let x;
        for (let i = 0; i < n_samples; ++i) {
            x = i * 2 / n_samples - 1;
            curve[i] = (3 + k) * x * 20 * deg / (Math.PI + k * Math.abs(x));
        }
        return curve;
    }

    setVolume(val) {
        this.volume = Math.max(0, Math.min(1, val));
        if (!this.muted) {
            this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
        }
    }

    setMute(muted) {
        this.muted = muted;
        if (this.muted) {
            this.masterGain.gain.setValueAtTime(0, this.ctx.currentTime);
        } else {
            this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
        }
    }

    resume() {
        if (this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
    }

    toggle(enabled) {
        this.enabled = enabled;
    }

    // Helper to create an oscillator with envelope
    playTone(freq, type, duration, vol = 1.0, slide = 0) {
        if (!this.enabled) return;
        this.resume();

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = type;
        osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
        if (slide !== 0) {
            osc.frequency.exponentialRampToValueAtTime(freq + slide, this.ctx.currentTime + duration);
        }

        gain.gain.setValueAtTime(vol, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + duration);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start();
        osc.stop(this.ctx.currentTime + duration);
    }

    // Helper for noise (snare/thud like)
    playNoise(duration, vol = 1.0, filterFreq = 1000) {
        if (!this.enabled) return;
        this.resume();

        const bufferSize = this.ctx.sampleRate * duration;
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }

        const noise = this.ctx.createBufferSource();
        noise.buffer = buffer;

        const filter = this.ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = filterFreq;

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(vol, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + duration);

        noise.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);

        noise.start();
    }

    // --- Electric Guitar Synth ---

    playGuitar(baseFreq, duration = 0.5, vol = 1.0) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        // 1. Source: Sawtooth (rich harmonics)
        const osc = this.ctx.createOscillator();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(baseFreq, t);

        // 2. Distortion (WaveShaper)
        const distortion = this.ctx.createWaveShaper();
        distortion.curve = this.distortionCurve;
        distortion.oversample = '4x';

        // 3. Filter (Lowpass to tame highs, maybe some Q/Resonance)
        const filter = this.ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(2000, t);
        filter.Q.value = 1.0;

        // 4. Envelope (Gain)
        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(0, t);
        gain.gain.linearRampToValueAtTime(vol, t + 0.05); // Fast attack
        gain.gain.exponentialRampToValueAtTime(vol * 0.5, t + 0.2); // Decay
        gain.gain.exponentialRampToValueAtTime(0.01, t + duration); // Release

        // Route: Osc -> Filter -> Distortion -> Gain -> Master
        // Placing distortion after filter changes character heavily.
        // Classic pedal chain: Guitar -> Distortion -> Amp (Filter/EQ)
        // Let's try: Osc -> Distortion -> Filter -> Gain

        osc.connect(distortion);
        distortion.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);

        osc.start(t);
        osc.stop(t + duration);

        // Add a second detuned oscillator for thickness (Chorus effect)
        const osc2 = this.ctx.createOscillator();
        osc2.type = 'sawtooth';
        osc2.frequency.setValueAtTime(baseFreq * 1.01, t); // Detune

        const gain2 = this.ctx.createGain();
        gain2.gain.setValueAtTime(0, t);
        gain2.gain.linearRampToValueAtTime(vol * 0.7, t + 0.05);
        gain2.gain.exponentialRampToValueAtTime(0.01, t + duration);

        const dist2 = this.ctx.createWaveShaper();
        dist2.curve = this.distortionCurve;

        osc2.connect(dist2);
        dist2.connect(filter); // Shared filter

        osc2.start(t);
        osc2.stop(t + duration);
    }

    // --- TR-808 Generators ---

    playKick(vol = 1.0, pitch = 1.0) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.frequency.setValueAtTime(150 * pitch, t);
        osc.frequency.exponentialRampToValueAtTime(40 * pitch, t + 0.5);

        gain.gain.setValueAtTime(vol, t);
        gain.gain.exponentialRampToValueAtTime(0.01, t + 0.5);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start(t);
        osc.stop(t + 0.5);

        // Click
        this.playNoise(0.01, vol * 0.5, 3000 * pitch);
    }

    playSnare(vol = 1.0, pitch = 1.0) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        // Tone
        const osc = this.ctx.createOscillator();
        const oscGain = this.ctx.createGain();
        osc.frequency.setValueAtTime(250 * pitch, t);
        osc.frequency.exponentialRampToValueAtTime(100 * pitch, t + 0.1);
        oscGain.gain.setValueAtTime(vol * 0.5, t);
        oscGain.gain.exponentialRampToValueAtTime(0.01, t + 0.1);
        osc.connect(oscGain);
        oscGain.connect(this.masterGain);
        osc.start(t);
        osc.stop(t + 0.1);

        // Noise (Snappy)
        const noise = this.ctx.createBufferSource();
        const bufferSize = this.ctx.sampleRate * 0.2;
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;
        noise.buffer = buffer;

        const noiseFilter = this.ctx.createBiquadFilter();
        noiseFilter.type = 'highpass';
        noiseFilter.frequency.value = 1000 * pitch;

        const noiseGain = this.ctx.createGain();
        noiseGain.gain.setValueAtTime(vol, t);
        noiseGain.gain.exponentialRampToValueAtTime(0.01, t + 0.2);

        noise.connect(noiseFilter);
        noiseFilter.connect(noiseGain);
        noiseGain.connect(this.masterGain);
        noise.start(t);
    }

    playHiHat(open = false, vol = 0.8, pitch = 1.0) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        // Simplified: High pass noise
        const noise = this.ctx.createBufferSource();
        const duration = open ? 0.3 : 0.05;
        const bufferSize = this.ctx.sampleRate * duration;
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;
        noise.buffer = buffer;

        const filter = this.ctx.createBiquadFilter();
        filter.type = 'highpass';
        filter.frequency.value = 7000 * pitch;

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(vol, t);
        gain.gain.exponentialRampToValueAtTime(0.01, t + duration);

        noise.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        noise.start(t);
    }

    playCowbell(vol = 0.8, pitch = 1.0) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;
        const duration = 0.3;

        // Two square waves
        const osc1 = this.ctx.createOscillator();
        const osc2 = this.ctx.createOscillator();
        osc1.type = 'square';
        osc2.type = 'square';
        osc1.frequency.value = 540 * pitch;
        osc2.frequency.value = 800 * pitch;

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(vol, t);
        gain.gain.exponentialRampToValueAtTime(0.01, t + duration);

        const filter = this.ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 1000 * pitch; // Resonant peak
        filter.Q.value = 1.0;

        osc1.connect(filter);
        osc2.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);

        osc1.start(t);
        osc2.start(t);
        osc1.stop(t + duration);
        osc2.stop(t + duration);
    }

    playClap(vol = 0.8, pitch = 1.0) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        const noise = this.ctx.createBufferSource();
        const duration = 0.2;
        const bufferSize = this.ctx.sampleRate * duration;
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;
        noise.buffer = buffer;

        const filter = this.ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 1500 * pitch;
        filter.Q.value = 1;

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(vol, t);
        // Clap envelope: multiple strikes
        gain.gain.setValueAtTime(0, t);
        gain.gain.linearRampToValueAtTime(vol, t + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.1, t + 0.03);
        gain.gain.setValueAtTime(vol, t + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.1, t + 0.06);
        gain.gain.setValueAtTime(vol, t + 0.06);
        gain.gain.exponentialRampToValueAtTime(0.001, t + duration);

        noise.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        noise.start(t);
    }

    // --- Game Sounds Mapped to 808 ---

    playFlipperUp(pitch = 1.0) {
        if (pitch >= 2.0) {
            // E2 = 82.41Hz. Let's use 82.41 * pitch.
            // If pitch is 2.0 (octave up), we play E3 (164.8Hz).
            // Let's align with the key of C Major from App.vue logic if possible, or just scale freq.
            this.playGuitar(55.0 * pitch, 0.6, 0.4); // Base A1 (55Hz)
        } else {
            // Swapped: Kick for flipper activation
            this.playKick(1.0, pitch);
        }
    }

    playFlipperDown(pitch = 1.0) {
        if (pitch >= 2.0) {
            // Muted palm mute release sound? Just a short chunks
            this.playGuitar(55.0 * pitch, 0.1, 0.2);
        } else {
            // Softer kick/tom for release
            this.playNoise(0.05, 0.2, 500 * pitch);
        }
    }

    playFlipperHit(pitch = 1.0) {
        // Heavy kick drum for flipper collision
        this.playKick(1.0, pitch * 0.8); // Slightly lower pitch for "heavy" feel
    }

    playBumper(pitch = 1.0) {
        if (pitch >= 2.0) {
            // Higher pitch power chord
            this.playGuitar(110.0 * pitch, 0.4, 0.5); // A2 base
        } else {
            // Swapped: Snare for bumpers
            this.playSnare(0.8, pitch);
        }
    }

    playWallHit(velocity = 1.0, pitch = 1.0) {
        // Tom or soft kick
        // Let's use a higher pitched kick/tom
        if (velocity > 0.5) {
            this.playKick(0.5, pitch * 1.5);
        } else {
            this.playNoise(0.01, 0.2, 1000 * pitch);
        }
    }

    playLaunch(pitch = 1.0) {
        if (pitch >= 2.0) {
            this.playGuitar(40.0 * pitch, 1.5, 0.6); // Long low note
        } else {
            // Open Hat + Kick
            this.playHiHat(true, 0.8, pitch);
            this.playKick(0.8, pitch);
        }
    }

    playDropTarget(pitch = 1.0) {
        // 808 Cowbell!
        this.playCowbell(0.8, pitch);
    }

    playRailHit(pitch = 1.0) {
        // Closed Hat
        this.playHiHat(false, 0.6, pitch);
    }

    playSlingshot(pitch = 1.0) {
        // Clap
        this.playClap(0.8, pitch);
    }
}

export default new SoundManager();
