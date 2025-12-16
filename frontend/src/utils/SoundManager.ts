interface MusicalScale {
    name: string;
    notes: number[];
    instrument: string;
    baseFreq: number;
    waveform: OscillatorType;
}

class SoundManager {
    ctx!: AudioContext;
    masterGain!: GainNode;
    volume!: number;
    muted!: boolean;
    enabled!: boolean;
    distortionCurve!: Float32Array;
    currentScaleIndex!: number;
    lastComboMilestone!: number;
    musicalScales!: MusicalScale[];
    alienResponseCallback?: () => void;
    matrixMode: boolean = false;
    dtmfRows: number[] = [697, 770, 852, 941];
    dtmfCols: number[] = [1209, 1336, 1477];
    currentMatrixSource: AudioBufferSourceNode | null = null;

    constructor() {
        try {
            console.log("SoundManager: Initializing...")
            this.ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
            this.masterGain = this.ctx.createGain();
            this.volume = 0.08;
            this.muted = false;
            this.masterGain.gain.value = this.volume;
            this.masterGain.connect(this.ctx.destination);
            this.enabled = true;

            // Pre-calculate distortion curve
            this.distortionCurve = this.makeDistortionCurve(400);

            // Track which musical scale/song mode we're in
            this.currentScaleIndex = 0;
            this.lastComboMilestone = 0;

            // Define different musical scales (semitones from root)
            // Each scale has unique instrument/tone characteristics
            this.musicalScales = [
                {
                    name: 'Major',
                    notes: [0, 2, 4, 5, 7, 9, 11, 12],
                    instrument: 'guitar',
                    baseFreq: 220, // A3
                    waveform: 'sawtooth'
                },
                {
                    name: 'Minor',
                    notes: [0, 2, 3, 5, 7, 8, 10, 12],
                    instrument: 'synth',
                    baseFreq: 196, // G3
                    waveform: 'triangle'
                },
                {
                    name: 'Pentatonic',
                    notes: [0, 2, 4, 7, 9, 12, 14, 16],
                    instrument: 'bell',
                    baseFreq: 261.63, // C4
                    waveform: 'sine'
                },
                {
                    name: 'Dorian',
                    notes: [0, 2, 3, 5, 7, 9, 10, 12],
                    instrument: 'organ',
                    baseFreq: 146.83, // D3
                    waveform: 'square'
                },
                {
                    name: 'Phrygian',
                    notes: [0, 1, 3, 5, 7, 8, 10, 12],
                    instrument: 'bass',
                    baseFreq: 164.81, // E3
                    waveform: 'sawtooth'
                },
                {
                    name: 'Mixolydian',
                    notes: [0, 2, 4, 5, 7, 9, 10, 12],
                    instrument: 'brass',
                    baseFreq: 196, // G3
                    waveform: 'sawtooth'
                },
                {
                    name: 'Harmonic Minor',
                    notes: [0, 2, 3, 5, 7, 8, 11, 12],
                    instrument: 'strings',
                    baseFreq: 220, // A3
                    waveform: 'triangle'
                },
                {
                    name: 'Blues',
                    notes: [0, 3, 5, 6, 7, 10, 12, 15],
                    instrument: 'guitar',
                    baseFreq: 110, // A2 (lower for bluesy feel)
                    waveform: 'sawtooth'
                },
                {
                    name: 'Katseye',
                    notes: [0, 3, 5, 7, 10, 12], // Trap/Phonk minor pentatonic
                    instrument: 'gnarly808',
                    baseFreq: 45, // Deep sub bass
                    waveform: 'sine'
                }
            ];

            console.log("SoundManager: Initialized successfully")
        } catch (e) {
            console.error("SoundManager: Initialization failed", e)
            this.enabled = false;
        }
    }

    makeDistortionCurve(amount: number) {
        const k = typeof amount === 'number' ? amount : 50,
            n_samples = 44100,
            curve = new Float32Array(n_samples) as any as Float32Array,
            deg = Math.PI / 180;
        let x;
        for (let i = 0; i < n_samples; ++i) {
            x = i * 2 / n_samples - 1;
            curve[i] = (3 + k) * x * 20 * deg / (Math.PI + k * Math.abs(x));
        }
        return curve;
    }

    // Hard clipping curve for aggressive 808s
    makeHardClipCurve(amount: number) {
        const k = amount;
        const n_samples = 44100;
        const curve = new Float32Array(n_samples) as any as Float32Array;
        for (let i = 0; i < n_samples; ++i) {
            let x = i * 2 / n_samples - 1;
            // Hard clip with some smoothing
            if (x > k) x = k;
            else if (x < -k) x = -k;
            curve[i] = x;
        }
        return curve;
    }

    setVolume(val: number) {
        this.volume = Math.max(0, Math.min(1, val));
        if (!this.muted) {
            this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
        }
    }

    setMute(muted: boolean) {
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

    toggle(enabled: boolean) {
        this.enabled = enabled;
    }

    setMatrixMode(enabled: boolean) {
        this.matrixMode = enabled;
        if (!enabled) {
            this.stopMatrixSounds();
        }
    }

    stopMatrixSounds() {
        if (this.currentMatrixSource) {
            try {
                this.currentMatrixSource.stop();
            } catch (e) {
                // Ignore if already stopped
            }
            this.currentMatrixSource = null;
        }
    }

    // Helper to create an oscillator with envelope
    playTone(freq: number, type: OscillatorType, duration: number, vol = 1.0, slide = 0) {
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
    playNoise(duration: number, vol = 1.0, filterFreq = 1000) {
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

    playGuitar(baseFreq: number, duration = 0.5, vol = 1.0) {
        // ... (existing playGuitar implementation) ...
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(baseFreq, t);
        const distortion = this.ctx.createWaveShaper();
        distortion.curve = this.distortionCurve as any;
        distortion.oversample = '4x';
        const filter = this.ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(Math.max(2000, baseFreq * 4), t);
        filter.Q.value = 1.0;
        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(0, t);
        gain.gain.linearRampToValueAtTime(vol, t + 0.05);
        gain.gain.exponentialRampToValueAtTime(vol * 0.5, t + 0.2);
        gain.gain.exponentialRampToValueAtTime(0.01, t + duration);
        osc.connect(distortion);
        distortion.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        osc.start(t);
        osc.stop(t + duration);
        const osc2 = this.ctx.createOscillator();
        osc2.type = 'sawtooth';
        osc2.frequency.setValueAtTime(baseFreq * 1.01, t);
        const gain2 = this.ctx.createGain();
        gain2.gain.setValueAtTime(0, t);
        gain2.gain.linearRampToValueAtTime(vol * 0.7, t + 0.05);
        gain2.gain.exponentialRampToValueAtTime(0.01, t + duration);
        const dist2 = this.ctx.createWaveShaper();
        dist2.curve = this.distortionCurve as any;
        osc2.connect(dist2);
        dist2.connect(filter);
        osc2.start(t);
        osc2.stop(t + duration);
    }

    // --- Gnarly 808 (Katseye Style) ---
    playGnarly808(baseFreq: number, duration = 0.8, vol = 1.0) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        // 1. Core Sub Oscillator (Sine for weight)
        const subOsc = this.ctx.createOscillator();
        subOsc.type = 'sine';
        // Pitch envelope: Start high, drop fast (the "kick" part)
        subOsc.frequency.setValueAtTime(baseFreq * 4, t);
        subOsc.frequency.exponentialRampToValueAtTime(baseFreq, t + 0.1);

        const subGain = this.ctx.createGain();
        subGain.gain.setValueAtTime(vol, t);
        subGain.gain.exponentialRampToValueAtTime(vol, t + 0.1); // Hold volume during punch
        subGain.gain.exponentialRampToValueAtTime(0.01, t + duration); // Long tail

        // 2. Distortion Layer (Triangle/Saw mix)
        const harmOsc = this.ctx.createOscillator();
        harmOsc.type = 'triangle';
        harmOsc.frequency.setValueAtTime(baseFreq * 4, t);
        harmOsc.frequency.exponentialRampToValueAtTime(baseFreq, t + 0.1);

        // Distortion chain
        const distortion = this.ctx.createWaveShaper();
        // Use a harder clipping curve for that "fried" sound
        distortion.curve = this.makeHardClipCurve(0.6) as any;
        distortion.oversample = '4x';

        const filter = this.ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(800, t); // Open up for harmonics
        filter.Q.value = 1;

        const harmGain = this.ctx.createGain();
        harmGain.gain.setValueAtTime(vol * 0.8, t);
        harmGain.gain.exponentialRampToValueAtTime(0.01, t + duration);

        // Connections
        subOsc.connect(subGain);
        subGain.connect(this.masterGain);

        harmOsc.connect(distortion);
        distortion.connect(filter);
        filter.connect(harmGain);
        harmGain.connect(this.masterGain);

        subOsc.start(t);
        subOsc.stop(t + duration);
        harmOsc.start(t);
        harmOsc.stop(t + duration);
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
        // Fix: Use the current scale's instrument instead of hardcoded threshold
        const scale = this.getCurrentScale();

        // Base frequency calculation to match the energy of the click
        // Guitar A2 (110) is a good base. 55Hz was too low.
        const baseFreq = 110.0 * pitch;

        // If pitch is significantly > 1.0, we are in a combo/multiplier. Play Music!
        if (pitch > 1.05) {
            switch (scale.instrument) {
                case 'guitar':
                    this.playGuitar(baseFreq, 0.4, 0.4);
                    break;
                case 'synth':
                    // Synth needs to be punchy
                    this.playInstrument(baseFreq, 'triangle', this.ctx.currentTime, 0.3, 0.4);
                    break;
                case 'bell':
                    this.playBell(baseFreq * 2, this.ctx.currentTime, 0.4, 0.5); // Bells sound better higher
                    break;
                case 'organ':
                    this.playOrgan(baseFreq, this.ctx.currentTime, 0.3, 0.4);
                    break;
                case 'bass':
                    this.playInstrument(baseFreq, 'sawtooth', this.ctx.currentTime, 0.3, 0.5);
                    break;
                case 'brass':
                    this.playBrass(baseFreq, this.ctx.currentTime, 0.3, 0.4);
                    break;
                case 'strings':
                    this.playStrings(baseFreq, this.ctx.currentTime, 0.4, 0.4);
                    break;
                case 'gnarly808':
                    this.playGnarly808(baseFreq, 0.5, 0.6);
                    break;
                default:
                    this.playGuitar(baseFreq, 0.4, 0.4);
            }
        } else {
            // Just starting / No combo - use the mechanical Kick sound
            this.playKick(1.0, pitch);
        }
    }

    playFlipperDown(pitch = 1.0) {
        if (pitch >= 1.05) {
            const scale = this.getCurrentScale();
            const baseFreq = 110.0 * pitch;

            // Muted release sound matching instrument (quieter/shorter)
            switch (scale.instrument) {
                case 'bell':
                    // Bells don't have "release" sounds really, simple click
                    this.playNoise(0.05, 0.1, 2000);
                    break;
                case 'gnarly808':
                    // Short, low thud for release
                    this.playKick(0.3, 0.5);
                    break;
                default:
                    // Muted guitar/synth release
                    this.playInstrument(baseFreq, 'sawtooth', this.ctx.currentTime, 0.1, 0.1);
            }
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
        if (this.matrixMode) {
            this.playRandomDTMF();
            return;
        }

        // Fix for "sporadic" notes: Drop the 2.0 threshold.
        // Use the same 1.05 threshold as flippers so entire scales play.
        const scale = this.getCurrentScale();
        const baseFreq = 110.0 * pitch;

        if (pitch > 1.05) {
            // Higher pitch power chord or instrument
            switch (scale.instrument) {
                case 'guitar':
                    this.playGuitar(baseFreq, 0.4, 0.5);
                    break;
                case 'synth':
                    this.playInstrument(baseFreq, 'sawtooth', this.ctx.currentTime, 0.3, 0.6);
                    break;
                case 'bell':
                    // Bells ring out longer
                    this.playBell(baseFreq * 2, this.ctx.currentTime, 0.6, 0.6);
                    break;
                case 'organ':
                    this.playOrgan(baseFreq, this.ctx.currentTime, 0.4, 0.5);
                    break;
                case 'gnarly808':
                    // Punchy short 808 for bumpers
                    this.playGnarly808(baseFreq * 2, 0.3, 0.6);
                    break;
                default:
                    this.playGuitar(baseFreq, 0.4, 0.5);
            }
        } else {
            // Swapped: Snare for bumpers (Mechanical/No Combo)
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
            this.playGuitar(40.0 * pitch, 1.5, 0.8); // Long low note, normalized vol
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

    playDestruction() {
        if (!this.enabled) return;
        // Heavy explosion sound: Low kick + Noise wash
        this.playKick(1.2, 0.5); // Deep impact
        this.playNoise(0.4, 0.6, 200); // Low rumble
        this.playNoise(0.2, 0.3, 1000); // Crunch
    }

    playRevolverRatchet(vol = 0.8) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        // Authentic revolver cocking using noise bursts for mechanical clicks
        // No oscillators - just transient mechanical sounds

        // 1. Initial hammer click (short, sharp noise burst)
        const hammerNoise = this.ctx.createBufferSource();
        const hammerBuffer = this.ctx.createBuffer(1, this.ctx.sampleRate * 0.03, this.ctx.sampleRate);
        const hammerData = hammerBuffer.getChannelData(0);
        for (let i = 0; i < hammerData.length; i++) {
            // Sharp attack, quick decay
            const envelope = Math.exp(-i / (this.ctx.sampleRate * 0.01));
            hammerData[i] = (Math.random() * 2 - 1) * envelope;
        }
        hammerNoise.buffer = hammerBuffer;

        const hammerFilter = this.ctx.createBiquadFilter();
        hammerFilter.type = 'bandpass';
        hammerFilter.frequency.value = 300;
        hammerFilter.Q.value = 2;

        const hammerGain = this.ctx.createGain();
        hammerGain.gain.value = vol * 0.7;

        hammerNoise.connect(hammerFilter);
        hammerFilter.connect(hammerGain);
        hammerGain.connect(this.masterGain);
        hammerNoise.start(t);

        // 2. Cylinder ratchet clicks (6 mechanical clicks, slower)
        for (let i = 0; i < 6; i++) {
            const clickTime = t + 0.1 + (i * 0.1); // 100ms between clicks

            // Create short click noise
            const clickNoise = this.ctx.createBufferSource();
            const clickBuffer = this.ctx.createBuffer(1, this.ctx.sampleRate * 0.02, this.ctx.sampleRate);
            const clickData = clickBuffer.getChannelData(0);

            for (let j = 0; j < clickData.length; j++) {
                // Very short transient
                const envelope = Math.exp(-j / (this.ctx.sampleRate * 0.005));
                clickData[j] = (Math.random() * 2 - 1) * envelope;
            }
            clickNoise.buffer = clickBuffer;

            // Filter for metallic click
            const clickFilter = this.ctx.createBiquadFilter();
            clickFilter.type = 'highpass';
            clickFilter.frequency.value = 800 + (i * 100); // Slight pitch variation

            const clickGain = this.ctx.createGain();
            clickGain.gain.value = vol * (0.5 - i * 0.04); // Gradually quieter

            clickNoise.connect(clickFilter);
            clickFilter.connect(clickGain);
            clickGain.connect(this.masterGain);
            clickNoise.start(clickTime);
        }

        // 3. Final lock "chunk" (heavier, lower click)
        const lockTime = t + 0.7;
        const lockNoise = this.ctx.createBufferSource();
        const lockBuffer = this.ctx.createBuffer(1, this.ctx.sampleRate * 0.05, this.ctx.sampleRate);
        const lockData = lockBuffer.getChannelData(0);

        for (let i = 0; i < lockData.length; i++) {
            const envelope = Math.exp(-i / (this.ctx.sampleRate * 0.015));
            lockData[i] = (Math.random() * 2 - 1) * envelope;
        }
        lockNoise.buffer = lockBuffer;

        const lockFilter = this.ctx.createBiquadFilter();
        lockFilter.type = 'lowpass';
        lockFilter.frequency.value = 400; // Lower, heavier sound
        lockFilter.Q.value = 1;

        const lockGain = this.ctx.createGain();
        lockGain.gain.value = vol * 0.9;

        lockNoise.connect(lockFilter);
        lockFilter.connect(lockGain);
        lockGain.connect(this.masterGain);
        lockNoise.start(lockTime);
    }

    // Handle 10x combo milestones
    checkComboMilestone(combo: number) {
        const milestone = Math.floor(combo / 10);

        if (milestone > this.lastComboMilestone && combo >= 10) {
            this.lastComboMilestone = milestone;
            this.currentScaleIndex = (this.currentScaleIndex + 1) % this.musicalScales.length;

            const newScale = this.musicalScales[this.currentScaleIndex];

            // Play a celebratory ascending melody in the new scale
            this.playMilestoneJingle(newScale);

            return true; // Milestone reached
        }
        return false;
    }

    setAlienResponseCallback(callback: () => void) {
        this.alienResponseCallback = callback;
    }

    // Play the Close Encounters five-note motif (D-E-C-C-G) followed by alien response
    playCloseEncounters(baseFreq = 293.66, onResponseCallback: (() => void) | null = null) { // D4 as base
        if (!this.enabled) return;
        this.resume();

        const t = this.ctx.currentTime;
        const noteDuration = 0.5;
        const gap = 0.05;

        // The iconic five notes: D4, E4, C4 (down octave), C3 (down octave), G3
        // Using clean sine waves like the original
        const humanMotif = [
            { freq: baseFreq, duration: noteDuration },           // D4 (293.66 Hz)
            { freq: baseFreq * Math.pow(2, 2 / 12), duration: noteDuration }, // E4
            { freq: baseFreq * Math.pow(2, -2 / 12), duration: noteDuration }, // C4
            { freq: baseFreq * Math.pow(2, -14 / 12), duration: noteDuration * 1.5 }, // C3 (lower octave, longer)
            { freq: baseFreq * Math.pow(2, -5 / 12), duration: noteDuration * 1.5 }  // G3 (longer)
        ];

        // Alien response: The iconic deep bass blast (shatters glass/blows lights)
        // A single, massive, low frequency tone
        const blastDuration = 2.5;

        let currentTime = t;

        // Play human motif
        humanMotif.forEach((note) => {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();

            osc.type = 'sine'; // Pure sine wave like the original
            osc.frequency.setValueAtTime(note.freq, currentTime);

            // Smooth envelope
            gain.gain.setValueAtTime(0, currentTime);
            gain.gain.linearRampToValueAtTime(0.6, currentTime + 0.05);
            gain.gain.setValueAtTime(0.6, currentTime + note.duration - 0.1);
            gain.gain.linearRampToValueAtTime(0, currentTime + note.duration);

            osc.connect(gain);
            gain.connect(this.masterGain);

            osc.start(currentTime);
            osc.stop(currentTime + note.duration);

            currentTime += note.duration + gap;
        });

        // Pause before alien response - dramatic pause
        currentTime += 0.5;

        // Determine which callback to use
        const callbackToUse = onResponseCallback || this.alienResponseCallback;

        if (callbackToUse) {
            setTimeout(() => {
                // ALIEN RESPONSE: The Brown Note / Horn
                // Two detuned sawtooths + sub sine + noise
                const osc1 = this.ctx.createOscillator();
                const osc2 = this.ctx.createOscillator();
                const subOsc = this.ctx.createOscillator();
                const noise = this.ctx.createBufferSource();

                // Frequencies - Raised to D2 (approx 73.4Hz) to reduce low-end distortion
                const freq = 73.4;

                osc1.type = 'sawtooth';
                osc2.type = 'sawtooth';
                subOsc.type = 'sine';

                osc1.frequency.value = freq;
                osc2.frequency.value = freq * 1.01; // Detune
                subOsc.frequency.value = freq / 2; // Sub-octave

                // Noise buffer
                const bSize = this.ctx.sampleRate * 2.0; // 2 seconds
                const bBuf = this.ctx.createBuffer(1, bSize, this.ctx.sampleRate);
                const bData = bBuf.getChannelData(0);
                for (let i = 0; i < bSize; i++) bData[i] = Math.random() * 2 - 1;
                noise.buffer = bBuf;

                // Mix Gain - Reduce overall gain slightly
                const mixGain = this.ctx.createGain();
                mixGain.gain.setValueAtTime(0, currentTime);
                mixGain.gain.linearRampToValueAtTime(0.8, currentTime + 0.1); // Attack (Reduced from 1.0)
                mixGain.gain.setValueAtTime(0.8, currentTime + 2.0 - 0.5);
                mixGain.gain.exponentialRampToValueAtTime(0.01, currentTime + 2.0);

                // Lowpass Filter for the "Foghorn" sound
                const lpf = this.ctx.createBiquadFilter();
                lpf.type = 'lowpass';
                lpf.frequency.setValueAtTime(200, currentTime);
                lpf.frequency.linearRampToValueAtTime(600, currentTime + 1.0); // Open up

                // Distortion for crunch - Reduce drive (was 400)
                const dist = this.ctx.createWaveShaper();
                dist.curve = this.makeDistortionCurve(100) as any;

                osc1.connect(lpf);
                osc2.connect(lpf);
                subOsc.connect(lpf);
                noise.connect(lpf);

                lpf.connect(dist);
                dist.connect(mixGain);
                mixGain.connect(this.masterGain);

                osc1.start(currentTime);
                osc2.start(currentTime);
                subOsc.start(currentTime);
                noise.start(currentTime);

                osc1.stop(currentTime + 2.0);
                osc2.stop(currentTime + 2.0);
                subOsc.stop(currentTime + 2.0);
                // noise.stop(currentTime + 2.0); 

                // Execute logic callback slightly before sound ends
                setTimeout(() => {
                    callbackToUse();
                }, (2.0 * 0.5) * 1000);

            }, (currentTime - t) * 1000); // Wait for sequence to finish
        }
    }

    // --- DTMF Helpers ---

    playDTMFPair(rowFreq: number, colFreq: number, duration: number = 0.1) {
        if (!this.enabled) return;
        this.resume();
        const t = this.ctx.currentTime;

        const osc1 = this.ctx.createOscillator();
        const osc2 = this.ctx.createOscillator();
        osc1.frequency.value = rowFreq;
        osc2.frequency.value = colFreq;

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(0.1, t);

        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(this.masterGain);

        osc1.start(t);
        osc2.start(t);
        osc1.stop(t + duration);
        osc2.stop(t + duration);
    }

    playRandomDTMF() {
        // Use local constants to avoid HMR state issues with class properties
        const dtmfRows = [697, 770, 852, 941];
        const dtmfCols = [1209, 1336, 1477];

        const r = dtmfRows[Math.floor(Math.random() * dtmfRows.length)];
        const c = dtmfCols[Math.floor(Math.random() * dtmfCols.length)];
        this.playDTMFPair(r, c, 0.15); // Slightly longer than dial sequence for impact
    }

    // --- Matrix Modem Sequence ---
    playModemSequence(): Promise<void> {
        if (!this.enabled) return Promise.resolve();
        this.resume();

        // Stop any existing matrix sound
        this.stopMatrixSounds();

        return new Promise((resolve) => {
            // Play the recorded dial-up sound for authenticity
            fetch('/sounds/dialup.ogg')
                .then(response => response.arrayBuffer())
                .then(arrayBuffer => this.ctx.decodeAudioData(arrayBuffer))
                .then(audioBuffer => {
                    const source = this.ctx.createBufferSource();
                    source.buffer = audioBuffer;
                    this.currentMatrixSource = source;

                    const gain = this.ctx.createGain();
                    gain.gain.value = 0.5; // Balanced with other sounds

                    source.connect(gain);
                    gain.connect(this.masterGain);

                    // When the sound hits the "connected" silence or finishes
                    source.onended = () => {
                        // Trigger AOL Voice Greetings
                        this.speakAOLGreeting();
                        resolve();
                    };

                    source.start();
                })
                .catch(e => {
                    console.error("Error playing dialup sound:", e);
                    resolve(); // Resolve anyway so we don't block
                });
        });
    }

    // Replacement for AOL Voice: Play construct.ogg
    speakAOLGreeting() {
        if (!this.enabled) return;
        this.resume();

        // Stop any existing matrix sound (e.g. modem if it didn't finish cleanly, which it should have)
        this.stopMatrixSounds();

        fetch('/sounds/construct.ogg')
            .then(response => response.arrayBuffer())
            .then(arrayBuffer => this.ctx.decodeAudioData(arrayBuffer))
            .then(audioBuffer => {
                const source = this.ctx.createBufferSource();
                source.buffer = audioBuffer;
                this.currentMatrixSource = source;

                const gain = this.ctx.createGain();
                gain.gain.value = 5.0; // Boosted source

                source.connect(gain);
                gain.connect(this.masterGain);

                source.start();
            })
            .catch(e => console.error("Error playing construct sound:", e));
    }

    // Play a celebratory jingle when reaching a combo milestone
    playMilestoneJingle(scale: MusicalScale) {
        if (!this.enabled) return;
        this.resume();

        // Every 3rd scale change (30 combo), play Close Encounters instead
        if (this.currentScaleIndex > 0 && this.currentScaleIndex % 3 === 0) {
            this.playCloseEncounters();
            return;
        }

        const baseFreq = scale.baseFreq || 220;
        const noteDuration = 0.15;
        const t = this.ctx.currentTime;

        // Play ascending scale rapidly with scale-specific instrument
        scale.notes.slice(0, 8).forEach((semitone: number, index: number) => {
            const startTime = t + (index * noteDuration * 0.5);
            const freq = baseFreq * Math.pow(2, semitone / 12);

            // Use different instruments based on scale
            switch (scale.instrument) {
                case 'guitar':
                    this.playGuitar(freq, noteDuration * 1.5, 0.7);
                    break;
                case 'synth':
                    this.playInstrument(freq, 'triangle', startTime, noteDuration, 0.5);
                    break;
                case 'bell':
                    this.playBell(freq, startTime, noteDuration, 0.6);
                    break;
                case 'organ':
                    this.playOrgan(freq, startTime, noteDuration, 0.5);
                    break;
                case 'bass':
                    this.playInstrument(freq * 0.5, 'sawtooth', startTime, noteDuration, 0.6);
                    break;
                case 'brass':
                    this.playBrass(freq, startTime, noteDuration, 0.6);
                    break;
                case 'strings':
                    this.playStrings(freq, startTime, noteDuration, 0.5);
                    break;
                case 'gnarly808':
                    this.playGnarly808(freq, noteDuration * 1.5, 0.7);
                    break;
                default:
                    this.playGuitar(freq, noteDuration * 1.5, 0.7);
            }
        });
    }

    // Generic instrument player with waveform selection
    playInstrument(freq: number, waveform: OscillatorType, startTime: number, duration: number, vol = 0.5) {
        if (!this.enabled) return;

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = waveform;
        osc.frequency.setValueAtTime(freq, startTime);

        gain.gain.setValueAtTime(vol, startTime);
        gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start(startTime);
        osc.stop(startTime + duration);
    }

    // Bell-like sound with harmonics
    playBell(freq: number, startTime: number, duration: number, vol = 0.5) {
        if (!this.enabled) return;

        // Multiple sine waves at harmonic intervals
        const harmonics = [1, 2.76, 5.4, 8.93]; // Bell-like ratios
        const amps = [1.0, 0.4, 0.2, 0.1];

        harmonics.forEach((ratio, i) => {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();

            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq * ratio, startTime);

            const amplitude = vol * amps[i];
            gain.gain.setValueAtTime(amplitude, startTime);
            gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration * 2);

            osc.connect(gain);
            gain.connect(this.masterGain);

            osc.start(startTime);
            osc.stop(startTime + duration * 2);
        });
    }

    // Organ sound with multiple harmonics
    playOrgan(freq: number, startTime: number, duration: number, vol = 0.5) {
        if (!this.enabled) return;

        // Organ has strong fundamental and octaves
        const harmonics = [1, 2, 4]; // Fundamental, octave, two octaves

        harmonics.forEach((ratio) => {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();

            osc.type = 'square';
            osc.frequency.setValueAtTime(freq * ratio, startTime);

            gain.gain.setValueAtTime(vol / harmonics.length, startTime);
            gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);

            osc.connect(gain);
            gain.connect(this.masterGain);

            osc.start(startTime);
            osc.stop(startTime + duration);
        });
    }

    // Brass-like sound with bright harmonics
    playBrass(freq: number, startTime: number, duration: number, vol = 0.5) {
        if (!this.enabled) return;

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        const filter = this.ctx.createBiquadFilter();

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(freq, startTime);

        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(freq * 3, startTime);
        filter.frequency.exponentialRampToValueAtTime(freq * 6, startTime + duration * 0.3);
        filter.Q.value = 2;

        gain.gain.setValueAtTime(vol, startTime);
        gain.gain.exponentialRampToValueAtTime(vol * 0.7, startTime + duration * 0.2);
        gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);

        osc.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);

        osc.start(startTime);
        osc.stop(startTime + duration);
    }

    // String ensemble sound
    playStrings(freq: number, startTime: number, duration: number, vol = 0.5) {
        if (!this.enabled) return;

        // Multiple detuned oscillators for string ensemble effect
        const detunes = [-5, 0, 5]; // Slight detuning in cents

        detunes.forEach((detune) => {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            const filter = this.ctx.createBiquadFilter();

            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(freq, startTime);
            osc.detune.setValueAtTime(detune, startTime);

            filter.type = 'lowpass';
            filter.frequency.setValueAtTime(freq * 4, startTime);
            filter.Q.value = 1;

            // Slow attack for strings
            gain.gain.setValueAtTime(0, startTime);
            gain.gain.linearRampToValueAtTime(vol / detunes.length, startTime + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);

            osc.connect(filter);
            filter.connect(gain);
            gain.connect(this.masterGain);

            osc.start(startTime);
            osc.stop(startTime + duration);
        });
    }

    // Get the current musical scale for pitch calculation
    getCurrentScale() {
        return this.musicalScales[this.currentScaleIndex];
    }

    // Reset scale when combo is lost (optional)
    resetScale() {
        this.currentScaleIndex = 0;
        this.lastComboMilestone = 0;
    }
}

export default new SoundManager();
