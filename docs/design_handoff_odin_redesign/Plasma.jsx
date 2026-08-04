const { useEffect, useRef } = React;

const hexToRgb = hex => {
  const r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
  if (!r) return [1, 0.5, 0.2];
  return [parseInt(r[1], 16) / 255, parseInt(r[2], 16) / 255, parseInt(r[3], 16) / 255];
};

const vertex = `#version 300 es
precision highp float;
in vec2 position;
in vec2 uv;
out vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const ORIGINAL_QUALITY = 60;

const buildFragment = () => `#version 300 es
precision highp float;
uniform vec2 iResolution;
uniform float iTime;
uniform vec3 uCustomColor;
uniform float uUseCustomColor;
uniform float uSpeed;
uniform float uDirection;
uniform float uScale;
uniform float uOpacity;
uniform vec2 uMouse;
uniform float uMouseInteractive;
uniform float uQuality;
uniform float uStepScale;
out vec4 fragColor;

void mainImage(out vec4 o, vec2 C) {
  vec2 center = iResolution.xy * 0.5;
  C = (C - center) / uScale + center;

  vec2 mouseOffset = (uMouse - center) * 0.0002;
  C += mouseOffset * length(C - center) * step(0.5, uMouseInteractive);

  float i, d, z, T = iTime * uSpeed * uDirection;
  vec3 O, p, S;

  for (vec2 r = iResolution.xy, Q; ++i < 60.0; O += o.w/d*o.xyz) {
    p = z*normalize(vec3(C-.5*r,r.y));
    p.z -= 4.;
    S = p;
    d = p.y-T;

    p.x += .4*(1.+p.y)*sin(d + p.x*0.1)*cos(.34*d + p.x*0.05);
    Q = p.xz *= mat2(cos(p.y+vec4(0,11,33,0)-T));
    z += d = (abs(sqrt(length(Q*Q)) - .25*(5.+S.y))/3.+8e-4) * uStepScale;
    o = 1.+sin(S.y+p.z*.5+S.z-length(S-p)+vec4(2,1,0,8));
    if (i >= uQuality) break;
  }

  o.xyz = tanh(O/1e4);
}

bool finite1(float x){ return !(isnan(x) || isinf(x)); }
vec3 sanitize(vec3 c){
  return vec3(
    finite1(c.r) ? c.r : 0.0,
    finite1(c.g) ? c.g : 0.0,
    finite1(c.b) ? c.b : 0.0
  );
}

void main() {
  vec4 o = vec4(0.0);
  mainImage(o, gl_FragCoord.xy);
  vec3 rgb = sanitize(o.rgb);

  float intensity = (rgb.r + rgb.g + rgb.b) / 3.0;
  vec3 customColor = intensity * uCustomColor;
  vec3 finalColor = mix(rgb, customColor, step(0.5, uUseCustomColor));

  float alpha = length(rgb) * uOpacity;
  fragColor = vec4(finalColor, alpha);
}`;

const waitForOgl = () => new Promise(resolve => {
  if (window.ogl && window.ogl.Renderer) return resolve(window.ogl);
  const t = setInterval(() => {
    if (window.ogl && window.ogl.Renderer) { clearInterval(t); resolve(window.ogl); }
  }, 60);
  setTimeout(() => { clearInterval(t); resolve(window.ogl); }, 8000);
});

const Plasma = ({
  color = '#ffffff',
  speed = 1,
  direction = 'forward',
  scale = 1,
  opacity = 1,
  mouseInteractive = false,
  renderScale = 0.5,
  maxDpr = 1.5,
  targetFps = 30,
  iterations = 44
}) => {
  const containerRef = useRef(null);
  const pendingMouse = useRef(null);

  useEffect(() => {
    const containerEl = containerRef.current;
    if (!containerEl) return;
    let disposed = false;
    let cleanup = () => {};

    waitForOgl().then(ogl => {
      if (disposed || !ogl || !ogl.Renderer) return;
      const { Renderer, Program, Mesh, Triangle } = ogl;
      const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const customColorRgb = hexToRgb(color);
      const directionMultiplier = direction === 'reverse' ? -1.0 : 1.0;

      let renderer;
      try {
        renderer = new Renderer({ webgl: 2, alpha: true, antialias: false, dpr: Math.min(window.devicePixelRatio || 1, maxDpr) });
      } catch (e) { return; }
      const gl = renderer.gl;
      if (!gl) return;
      const canvas = gl.canvas;
      canvas.style.display = 'block';
      canvas.style.width = '100%';
      canvas.style.height = '100%';
      containerEl.appendChild(canvas);

      const program = new Program(gl, {
        vertex,
        fragment: buildFragment(),
        uniforms: {
          iTime: { value: 0 },
          iResolution: { value: new Float32Array([1, 1]) },
          uCustomColor: { value: new Float32Array(customColorRgb) },
          uUseCustomColor: { value: color ? 1.0 : 0.0 },
          uSpeed: { value: speed * 0.4 },
          uDirection: { value: directionMultiplier },
          uScale: { value: scale },
          uOpacity: { value: opacity },
          uMouse: { value: new Float32Array([0, 0]) },
          uMouseInteractive: { value: mouseInteractive ? 1.0 : 0.0 },
          uQuality: { value: iterations },
          uStepScale: { value: ORIGINAL_QUALITY / iterations }
        }
      });
      const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });

      const handleMouseMove = e => {
        const rect = containerEl.getBoundingClientRect();
        pendingMouse.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      };
      if (mouseInteractive) containerEl.addEventListener('mousemove', handleMouseMove, { passive: true });

      let resizePending = false;
      const setSize = () => {
        const rect = containerEl.getBoundingClientRect();
        renderer.setSize(Math.max(1, Math.floor(rect.width * renderScale)), Math.max(1, Math.floor(rect.height * renderScale)));
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        const res = program.uniforms.iResolution.value;
        res[0] = gl.drawingBufferWidth;
        res[1] = gl.drawingBufferHeight;
      };
      const ro = new ResizeObserver(() => {
        if (resizePending) return;
        resizePending = true;
        requestAnimationFrame(() => { resizePending = false; setSize(); });
      });
      ro.observe(containerEl);
      setSize();

      let raf = 0, contextLost = false, isVisible = true;
      let tabVisible = document.visibilityState !== 'hidden';
      const t0 = performance.now();
      const frameInterval = 1000 / targetFps;
      let lastFrameTime = 0;

      const loop = t => {
        if (contextLost || !isVisible || !tabVisible) return;
        if (t - lastFrameTime < frameInterval) { raf = requestAnimationFrame(loop); return; }
        lastFrameTime = t;
        if (pendingMouse.current) {
          const m = program.uniforms.uMouse.value;
          m[0] = pendingMouse.current.x;
          m[1] = pendingMouse.current.y;
          pendingMouse.current = null;
        }
        const timeValue = (t - t0) * 0.001;
        if (direction === 'pingpong') {
          const dur = 10;
          const seg = timeValue % dur;
          const fwd = Math.floor(timeValue / dur) % 2 === 0;
          const u = seg / dur;
          const smooth = u * u * (3 - 2 * u);
          program.uniforms.uDirection.value = 1.0;
          program.uniforms.iTime.value = fwd ? smooth * dur : (1 - smooth) * dur;
        } else {
          program.uniforms.iTime.value = timeValue;
        }
        renderer.render({ scene: mesh });
        raf = requestAnimationFrame(loop);
      };

      const onLost = e => { e.preventDefault(); contextLost = true; cancelAnimationFrame(raf); };
      const onRestored = () => {
        contextLost = false;
        if (isVisible && tabVisible && !prefersReducedMotion) { cancelAnimationFrame(raf); raf = requestAnimationFrame(loop); }
      };
      canvas.addEventListener('webglcontextlost', onLost);
      canvas.addEventListener('webglcontextrestored', onRestored);

      const io = new IntersectionObserver(([entry]) => {
        const was = isVisible;
        isVisible = entry.isIntersecting;
        if (isVisible && !was && !contextLost && tabVisible && !prefersReducedMotion) { cancelAnimationFrame(raf); raf = requestAnimationFrame(loop); }
      }, { threshold: 0 });
      io.observe(containerEl);

      const onVis = () => {
        tabVisible = document.visibilityState !== 'hidden';
        if (tabVisible && isVisible && !contextLost && !prefersReducedMotion) { cancelAnimationFrame(raf); lastFrameTime = 0; raf = requestAnimationFrame(loop); }
        else cancelAnimationFrame(raf);
      };
      document.addEventListener('visibilitychange', onVis);

      if (prefersReducedMotion) { program.uniforms.iTime.value = 0; renderer.render({ scene: mesh }); }
      else raf = requestAnimationFrame(loop);

      cleanup = () => {
        cancelAnimationFrame(raf);
        ro.disconnect();
        io.disconnect();
        document.removeEventListener('visibilitychange', onVis);
        canvas.removeEventListener('webglcontextlost', onLost);
        canvas.removeEventListener('webglcontextrestored', onRestored);
        if (mouseInteractive) containerEl.removeEventListener('mousemove', handleMouseMove);
        try { containerEl.removeChild(canvas); } catch (e) {}
      };
    });

    return () => { disposed = true; cleanup(); };
  }, [color, speed, direction, scale, opacity, mouseInteractive, renderScale, maxDpr, targetFps, iterations]);

  return React.createElement('div', { ref: containerRef, style: { position: 'relative', width: '100%', height: '100%', overflow: 'hidden' } });
};

module.exports = { Plasma };
