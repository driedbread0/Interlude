import { useEffect, useRef } from "react";

/*
 * Adapted from ReactBits Pixel Blast for Interlude's non-interactive ambient field.
 * The documented diamond shader is retained, while native WebGL avoids a 3D-engine
 * payload for a single full-screen plane. Ripple and liquid branches stay disabled.
 */

const SHAPE_MAP = {
  square: 0,
  circle: 1,
  triangle: 2,
  diamond: 3,
};

const VERTEX_SHADER = `#version 300 es
in vec2 position;

void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

uniform vec3 uColor;
uniform vec2 uResolution;
uniform float uTime;
uniform float uPixelSize;
uniform float uScale;
uniform float uDensity;
uniform float uPixelJitter;
uniform float uEdgeFade;
uniform int uShapeType;

out vec4 fragColor;

float bayer2(vec2 point) {
  point = floor(point);
  return fract(point.x / 2.0 + point.y * point.y * 0.75);
}

#define BAYER4(point) (bayer2(0.5 * (point)) * 0.25 + bayer2(point))
#define BAYER8(point) (BAYER4(0.5 * (point)) * 0.25 + bayer2(point))

float hash11(float value) {
  return fract(sin(value) * 43758.5453);
}

float valueNoise(vec3 point) {
  vec3 integerPoint = floor(point);
  vec3 fractionalPoint = fract(point);
  float n000 = hash11(dot(integerPoint + vec3(0.0, 0.0, 0.0), vec3(1.0, 57.0, 113.0)));
  float n100 = hash11(dot(integerPoint + vec3(1.0, 0.0, 0.0), vec3(1.0, 57.0, 113.0)));
  float n010 = hash11(dot(integerPoint + vec3(0.0, 1.0, 0.0), vec3(1.0, 57.0, 113.0)));
  float n110 = hash11(dot(integerPoint + vec3(1.0, 1.0, 0.0), vec3(1.0, 57.0, 113.0)));
  float n001 = hash11(dot(integerPoint + vec3(0.0, 0.0, 1.0), vec3(1.0, 57.0, 113.0)));
  float n101 = hash11(dot(integerPoint + vec3(1.0, 0.0, 1.0), vec3(1.0, 57.0, 113.0)));
  float n011 = hash11(dot(integerPoint + vec3(0.0, 1.0, 1.0), vec3(1.0, 57.0, 113.0)));
  float n111 = hash11(dot(integerPoint + vec3(1.0, 1.0, 1.0), vec3(1.0, 57.0, 113.0)));
  vec3 weight = fractionalPoint * fractionalPoint * fractionalPoint * (fractionalPoint * (fractionalPoint * 6.0 - 15.0) + 10.0);
  float x00 = mix(n000, n100, weight.x);
  float x10 = mix(n010, n110, weight.x);
  float x01 = mix(n001, n101, weight.x);
  float x11 = mix(n011, n111, weight.x);
  return mix(mix(x00, x10, weight.y), mix(x01, x11, weight.y), weight.z) * 2.0 - 1.0;
}

float fbm(vec2 uv, float time) {
  vec3 point = vec3(uv * uScale, time);
  float amplitude = 1.0;
  float frequency = 1.0;
  float sum = 1.0;

  for (int octave = 0; octave < 5; octave += 1) {
    sum += amplitude * valueNoise(point * frequency);
    frequency *= 1.25;
  }

  return sum * 0.5 + 0.5;
}

float circleMask(vec2 point, float coverage) {
  float radius = sqrt(coverage) * 0.25;
  float distanceFromEdge = length(point - 0.5) - radius;
  float antialiasWidth = 0.5 * fwidth(distanceFromEdge);
  return coverage * (1.0 - smoothstep(-antialiasWidth, antialiasWidth, distanceFromEdge * 2.0));
}

float triangleMask(vec2 point, vec2 pixelId, float coverage) {
  if (mod(pixelId.x + pixelId.y, 2.0) > 0.5) point.x = 1.0 - point.x;
  float radius = sqrt(coverage);
  float distanceFromEdge = point.y - radius * (1.0 - point.x);
  return coverage * clamp(0.5 - distanceFromEdge / fwidth(distanceFromEdge), 0.0, 1.0);
}

float diamondMask(vec2 point, float coverage) {
  float radius = sqrt(coverage) * 0.564;
  return step(abs(point.x - 0.49) + abs(point.y - 0.49), radius);
}

void main() {
  vec2 fragment = gl_FragCoord.xy - uResolution * 0.5;
  vec2 pixelId = floor(fragment / uPixelSize);
  vec2 pixelUv = fract(fragment / uPixelSize);
  float cellSize = 8.0 * uPixelSize;
  vec2 cell = floor(fragment / cellSize) * cellSize;
  float aspectRatio = uResolution.x / uResolution.y;
  vec2 uv = cell / uResolution * vec2(aspectRatio, 1.0);

  float base = fbm(uv, uTime * 0.05) * 0.5 - 0.65;
  float feed = base + (uDensity - 0.5) * 0.3;
  float orderedDither = BAYER8(fragment / uPixelSize) - 0.5;
  float activated = step(0.5, feed + orderedDither);
  float randomValue = fract(sin(dot(pixelId, vec2(127.1, 311.7))) * 43758.5453);
  float coverage = activated * (1.0 + (randomValue - 0.5) * uPixelJitter);
  float mask;

  if (uShapeType == 1) mask = circleMask(pixelUv, coverage);
  else if (uShapeType == 2) mask = triangleMask(pixelUv, pixelId, coverage);
  else if (uShapeType == 3) mask = diamondMask(pixelUv, coverage);
  else mask = coverage;

  if (uEdgeFade > 0.0) {
    vec2 normalized = gl_FragCoord.xy / uResolution;
    float edge = min(min(normalized.x, normalized.y), min(1.0 - normalized.x, 1.0 - normalized.y));
    mask *= smoothstep(0.0, uEdgeFade, edge);
  }

  fragColor = vec4(uColor, mask);
}
`;

function compileShader(gl, type, source) {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);

  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.warn("Pixel Blast shader could not be compiled.", gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function createProgram(gl) {
  const vertexShader = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  if (!vertexShader || !fragmentShader) return null;

  const program = gl.createProgram();
  if (!program) return null;
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);
  gl.deleteShader(vertexShader);
  gl.deleteShader(fragmentShader);

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.warn("Pixel Blast program could not be linked.", gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }
  return program;
}

function hexToRgb(hex) {
  const normalized = hex.replace("#", "");
  const value = Number.parseInt(normalized.length === 3
    ? normalized.split("").map((character) => character + character).join("")
    : normalized, 16);
  return [((value >> 16) & 255) / 255, ((value >> 8) & 255) / 255, (value & 255) / 255];
}

export default function PixelBlast({
  className = "",
  color = "#B9AA93",
  edgeFade = 0,
  patternDensity = 0.55,
  patternScale = 2.75,
  pixelSize = 2,
  pixelSizeJitter = 0,
  speed = 0.1,
  variant = "diamond",
}) {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2", { alpha: true, antialias: false, powerPreference: "high-performance" });
    if (!gl) return undefined;

    const program = createProgram(gl);
    if (!program) return undefined;

    const position = gl.getAttribLocation(program, "position");
    const buffer = gl.createBuffer();
    if (!buffer || position < 0) {
      gl.deleteProgram(program);
      return undefined;
    }

    const uniform = (name) => gl.getUniformLocation(program, name);
    const uniforms = {
      color: uniform("uColor"),
      density: uniform("uDensity"),
      edgeFade: uniform("uEdgeFade"),
      pixelJitter: uniform("uPixelJitter"),
      pixelSize: uniform("uPixelSize"),
      resolution: uniform("uResolution"),
      scale: uniform("uScale"),
      shapeType: uniform("uShapeType"),
      time: uniform("uTime"),
    };

    container.appendChild(canvas);
    canvas.style.height = "100%";
    canvas.style.width = "100%";

    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
      -1, -1, 1, -1, -1, 1,
      -1, 1, 1, -1, 1, 1,
    ]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    gl.clearColor(0, 0, 0, 0);

    const [red, green, blue] = hexToRgb(color);
    gl.uniform3f(uniforms.color, red, green, blue);
    gl.uniform1f(uniforms.density, patternDensity);
    gl.uniform1f(uniforms.edgeFade, edgeFade);
    gl.uniform1f(uniforms.pixelJitter, pixelSizeJitter);
    gl.uniform1f(uniforms.scale, patternScale);
    gl.uniform1i(uniforms.shapeType, SHAPE_MAP[variant] ?? SHAPE_MAP.diamond);

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const timeOffset = Math.random() * 1000;
    const startTime = performance.now();
    let animationFrame = 0;
    let stopped = false;

    const renderFrame = (now = startTime) => {
      if (stopped) return;
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(uniforms.time, timeOffset + ((now - startTime) / 1000) * speed);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    };

    const animate = (now) => {
      renderFrame(now);
      if (!reduceMotion.matches && !document.hidden) animationFrame = requestAnimationFrame(animate);
    };

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.round(container.clientWidth * ratio));
      canvas.height = Math.max(1, Math.round(container.clientHeight * ratio));
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(uniforms.resolution, canvas.width, canvas.height);
      gl.uniform1f(uniforms.pixelSize, pixelSize * ratio);
      renderFrame();
    };

    const restart = () => {
      cancelAnimationFrame(animationFrame);
      if (reduceMotion.matches || document.hidden) {
        renderFrame();
      } else {
        animationFrame = requestAnimationFrame(animate);
      }
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    reduceMotion.addEventListener("change", restart);
    document.addEventListener("visibilitychange", restart);
    resize();
    restart();

    return () => {
      stopped = true;
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      reduceMotion.removeEventListener("change", restart);
      document.removeEventListener("visibilitychange", restart);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
      canvas.remove();
    };
  }, [color, edgeFade, patternDensity, patternScale, pixelSize, pixelSizeJitter, speed, variant]);

  return <div ref={containerRef} aria-hidden="true" className={`pixel-blast-container ${className}`} />;
}
