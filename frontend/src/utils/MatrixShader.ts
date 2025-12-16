import * as THREE from 'three';

export const MatrixShader = {
    uniforms: {
        time: { value: 1.0 },
        resolution: { value: new THREE.Vector2() },
        color: { value: new THREE.Color(0x00ff00) }
    },
    vertexShader: `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    fragmentShader: `
        varying vec2 vUv;
        uniform float time;
        uniform vec3 color;

        float random(vec2 st) {
            return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
        }

        void main() {
            // Grid size for the "characters"
            vec2 grid = vec2(50.0, 20.0);
            vec2 st = vUv * grid;
            vec2 ipos = floor(st);
            vec2 fpos = fract(st);

            // Falling speed depends on column
            float speed = 2.0 + random(vec2(ipos.x, 0.0)) * 10.0;
            float y = mod(time * speed + ipos.y, grid.y);
            
            // Trail effect
            float brightness = 1.0 - (y / (grid.y * 0.5));
            brightness = clamp(brightness, 0.0, 1.0);

            // Random "character" flickering
            float charFlicker = step(0.5, random(vec2(ipos.x, floor(time * 10.0 + ipos.y))));
            
            // Glitch/Head effect (bright leading edge)
            if (y < 2.0) brightness = 1.0;

            vec3 finalColor = color * brightness * charFlicker;

            // Simple blocky character shape (just borders/noise within the cell)
            float charShape = step(0.2, random(ipos));
            
            gl_FragColor = vec4(finalColor * charShape, 1.0);
        }
    `
};
