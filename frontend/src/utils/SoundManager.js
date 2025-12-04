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
            console.log("SoundManager: Initialized successfully")
        } catch (e) {
            console.error("SoundManager: Initialization failed", e)
            this.enabled = false;
        }
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

    // --- TR-808 Generators ---

    playKick(vol = 1.0) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.frequency.setValueAtTime(150, t);
        osc.frequency.exponentialRampToValueAtTime(40, t + 0.5);

        gain.gain.setValueAtTime(vol, t);
        gain.gain.exponentialRampToValueAtTime(0.01, t + 0.5);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start(t);
        osc.stop(t + 0.5);

        // Click
        this.playNoise(0.01, vol * 0.5, 3000);
    }

    playSnare(vol = 1.0) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        // Tone
        const osc = this.ctx.createOscillator();
        const oscGain = this.ctx.createGain();
        osc.frequency.setValueAtTime(250, t);
        osc.frequency.exponentialRampToValueAtTime(100, t + 0.1);
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
        noiseFilter.frequency.value = 1000;

        const noiseGain = this.ctx.createGain();
        noiseGain.gain.setValueAtTime(vol, t);
        noiseGain.gain.exponentialRampToValueAtTime(0.01, t + 0.2);

        noise.connect(noiseFilter);
        noiseFilter.connect(noiseGain);
        noiseGain.connect(this.masterGain);
        noise.start(t);
    }

    playHiHat(open = false, vol = 0.8) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        // 808 Hat is actually 6 square waves, but we'll approximate with high-passed noise + metallic ring
        const fundamental = 400;
        const ratios = [2, 3, 4.16, 5.43, 6.79, 8.21];

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
        filter.frequency.value = 7000;

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(vol, t);
        gain.gain.exponentialRampToValueAtTime(0.01, t + duration);

        noise.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        noise.start(t);
    }

    playCowbell(vol = 0.8) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;
        const duration = 0.3;

        // Two square waves
        const osc1 = this.ctx.createOscillator();
        const osc2 = this.ctx.createOscillator();
        osc1.type = 'square';
        osc2.type = 'square';
        osc1.frequency.value = 540;
        osc2.frequency.value = 800;

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(vol, t);
        gain.gain.exponentialRampToValueAtTime(0.01, t + duration);

        const filter = this.ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 1000; // Resonant peak
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

    playClap(vol = 0.8) {
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
        filter.frequency.value = 1500;
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

    playFlipperUp() {
        // Snare for punchy flip
        this.playSnare(0.8);
    }

    playFlipperDown() {
        // Softer kick/tom for release
        // this.playKick(0.3);
        // Or just a quiet noise
        this.playNoise(0.05, 0.2, 500);
    }

    playBumper() {
        // 808 Kick for bumpers (Boom!)
        this.playKick(1.0);
    }

    playWallHit(velocity = 1.0) {
        // Tom or soft kick
        // Let's use a higher pitched kick/tom
        if (velocity > 0.5) {
            this.playKick(0.5);
        } else {
            this.playNoise(0.01, 0.2, 1000);
        }
    }

    playLaunch() {
        // Open Hat + Kick
        this.playHiHat(true, 0.8);
        this.playKick(0.8);
    }

    playDropTarget() {
        // 808 Cowbell!
        this.playCowbell(0.8);
    }

    playRailHit() {
        // Closed Hat
        this.playHiHat(false, 0.6);
    }

    playSlingshot() {
        // Clap
        this.playClap(0.8);
    }
}

export default new SoundManager();
