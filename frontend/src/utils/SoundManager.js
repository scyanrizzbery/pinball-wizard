class SoundManager {
    constructor() {
        try {
            console.log("SoundManager: Initializing...")
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
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
            ];

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
        // Open filter for higher notes to avoid silencing them
        // Keep at least 2000Hz for body, but scale up with pitch
        filter.frequency.setValueAtTime(Math.max(2000, baseFreq * 4), t);
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
                default:
                    this.playGuitar(baseFreq, 0.4, 0.4);
            }
        } else {
            // Just starting / No combo - use the mechanical Kick sound
            this.playKick(1.0, pitch);
        }
    }

    playFlipperDown(pitch = 1.0) {
        if (pitch > 1.05) {
            const scale = this.getCurrentScale();
            const baseFreq = 110.0 * pitch;

            // Muted release sound matching instrument (quieter/shorter)
            switch (scale.instrument) {
                case 'bell':
                    // Bells don't have "release" sounds really, simple click
                    this.playNoise(0.05, 0.1, 2000);
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

    // Handle 10x combo milestones
    checkComboMilestone(combo) {
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

    // Play the Close Encounters five-note motif (D-E-C-C-G)
    playCloseEncounters(baseFreq = 293.66) { // D4 as base
        if (!this.enabled) return;
        this.resume();

        const t = this.ctx.currentTime;
        const noteDuration = 0.5;
        const gap = 0.05;

        // The iconic five notes: D4, E4, C4 (down octave), C3 (down octave), G3
        // Using clean sine waves like the original
        const motif = [
            { freq: baseFreq, duration: noteDuration },           // D4 (293.66 Hz)
            { freq: baseFreq * Math.pow(2, 2 / 12), duration: noteDuration }, // E4
            { freq: baseFreq * Math.pow(2, -2 / 12), duration: noteDuration }, // C4
            { freq: baseFreq * Math.pow(2, -14 / 12), duration: noteDuration * 1.5 }, // C3 (lower octave, longer)
            { freq: baseFreq * Math.pow(2, -5 / 12), duration: noteDuration * 1.5 }  // G3 (longer)
        ];

        let currentTime = t;
        motif.forEach((note) => {
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

        console.log('🛸 Close Encounters motif played!');
    }

    // Play a celebratory jingle when reaching a combo milestone
    playMilestoneJingle(scale) {
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
        scale.notes.slice(0, 8).forEach((semitone, index) => {
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
                default:
                    this.playGuitar(freq, noteDuration * 1.5, 0.7);
            }
        });
    }

    // Generic instrument player with waveform selection
    playInstrument(freq, waveform, startTime, duration, vol = 0.5) {
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
    playBell(freq, startTime, duration, vol = 0.5) {
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
    playOrgan(freq, startTime, duration, vol = 0.5) {
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
    playBrass(freq, startTime, duration, vol = 0.5) {
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
    playStrings(freq, startTime, duration, vol = 0.5) {
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
