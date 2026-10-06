import { Component, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import './Orb.css'

export type OrbMode = 'idle' | 'listening' | 'thinking' | 'speaking'

interface OrbProps {
  mode: OrbMode
  /** Normalized volume from the microphone or the audio being played, never a simulated waveform. */
  audioLevel: number
  reducedMotion?: boolean
  quality?: 'auto' | 'low' | 'high'
  accent?: 'cyan' | 'violet' | 'emerald' | 'amber'
}

const PALETTES: Record<OrbMode, [string, string, string]> = {
  idle: ['#537dd1', '#b7cfff', '#9983dc'],
  listening: ['#4b92c9', '#b1e7ed', '#8f9bde'],
  thinking: ['#726cc9', '#d2caff', '#899bdd'],
  speaking: ['#608ade', '#c4e0ff', '#b095e7'],
}

const ACCENT_PALETTES: Record<NonNullable<OrbProps['accent']>, [string, string, string]> = {
  cyan: PALETTES.idle,
  violet: ['#7865bd', '#d4caff', '#91a4e2'],
  emerald: ['#448f9b', '#b5e9e4', '#899bdf'],
  amber: ['#a48d6f', '#ecdec1', '#a09ade'],
}

const vertexShader = /* glsl */ `
  uniform float uTime;
  uniform float uAmplitude;
  uniform float uActivity;
  varying vec3 vPosition;
  varying vec3 vWorldPosition;
  varying vec3 vNormal;

  void main() {
    // A sphere keeps its silhouette; voice only introduces a small surface ripple.
    float wave = sin(position.y * 5.0 + uTime * 1.4)
      * sin(position.x * 4.0 - uTime * 0.8)
      * sin(position.z * 3.0 + uTime * 0.55);
    float deformation = wave * (0.004 + uActivity * 0.004 + uAmplitude * 0.016);
    vec3 transformed = position + normal * deformation;
    vPosition = transformed;
    vec4 world = modelMatrix * vec4(transformed, 1.0);
    vWorldPosition = world.xyz;
    vNormal = normalize(mat3(modelMatrix) * normal);
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`

const fragmentShader = /* glsl */ `
  uniform float uTime;
  uniform float uAmplitude;
  uniform float uActivity;
  uniform vec3 uBody;
  uniform vec3 uLight;
  uniform vec3 uPearl;
  varying vec3 vPosition;
  varying vec3 vWorldPosition;
  varying vec3 vNormal;

  float hash(vec3 p) {
    p = fract(p * 0.3183099 + vec3(0.1, 0.3, 0.5));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
  }

  float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(mix(hash(i), hash(i + vec3(1, 0, 0)), f.x),
          mix(hash(i + vec3(0, 1, 0)), hash(i + vec3(1, 1, 0)), f.x), f.y),
      mix(mix(hash(i + vec3(0, 0, 1)), hash(i + vec3(1, 0, 1)), f.x),
          mix(hash(i + vec3(0, 1, 1)), hash(i + vec3(1, 1, 1)), f.x), f.y), f.z);
  }

  void main() {
    vec3 N = normalize(vNormal);
    vec3 V = normalize(cameraPosition - vWorldPosition);
    float facing = max(dot(N, V), 0.0);
    float fresnel = pow(1.0 - facing, 3.2);
    vec3 reflected = reflect(-V, N);

    // Refracted, layered color moves inside the glass instead of orbiting outside it.
    vec3 p = vPosition * 1.8;
    float drift = uTime * (0.065 + uActivity * 0.04);
    p.y += drift;
    float warp = noise(p * 1.5 + vec3(drift * 0.3, 0.0, -drift));
    float fluid = sin(p.y * 2.3 + p.x * 1.5 + warp * 4.5 + drift);
    float ribbon = pow(1.0 - abs(fluid), 3.0);
    float layer = noise(p * 2.5 - vec3(0.0, drift, 0.0));
    float pearl = smoothstep(0.28, 0.83, layer + vPosition.x * 0.15);

    vec3 color = mix(uBody * 0.36, uBody * 0.85, facing);
    color = mix(color, uPearl * 0.82, pearl * (0.15 + facing * 0.34));
    color += uLight * ribbon * (0.14 + uAmplitude * 0.11) * facing;
    color += uLight * pow(max(0.0, 1.0 - abs(fluid * 0.7 + 0.33)), 9.0) * 0.065;

    // Broad studio reflections and fine clearcoat give the volume a glass surface.
    vec3 key = normalize(vec3(-0.65, 0.9, 0.85));
    float diffuse = max(dot(N, key), 0.0);
    color *= 0.6 + diffuse * 0.65;
    float softbox = pow(max(dot(reflected, key), 0.0), 26.0);
    float clearcoat = pow(max(dot(reflected, key), 0.0), 90.0);
    float sheen = pow(max(dot(reflected, normalize(vec3(0.7, -0.25, 0.75))), 0.0), 48.0);
    color += vec3(0.88, 0.93, 1.0) * (softbox * 0.68 + clearcoat * 0.5);
    color += uPearl * sheen * 0.5;
    float rimLight = 0.18 + pow(max(dot(N, normalize(vec3(-0.7, 0.3, 0.2))), 0.0), 2.0) * 0.72;
    color += mix(uPearl, uLight, N.x * 0.5 + 0.5) * fresnel * rimLight;

    // A delicate refraction edge leaves the silhouette crisp and dimensional.
    color += uLight * pow(1.0 - facing, 11.0) * 0.22;
    gl_FragColor = vec4(color, 0.98);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`

function GlassSphere({ mode, audioLevel, reducedMotion, quality, accent = 'cyan', pointer }: OrbProps & {
  pointer: React.RefObject<{ x: number; y: number }>
}) {
  const mesh = useRef<THREE.Mesh>(null)
  const amplitude = useRef(0)
  const motionTime = useRef(0)
  const invalidate = useThree(state => state.invalidate)
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uAmplitude: { value: 0 },
    uActivity: { value: 0 },
    uBody: { value: new THREE.Color(PALETTES.idle[0]) },
    uLight: { value: new THREE.Color(PALETTES.idle[1]) },
    uPearl: { value: new THREE.Color(PALETTES.idle[2]) },
  }), [])
  const targetColors = useMemo(() => (mode === 'idle' || mode === 'speaking'
    ? ACCENT_PALETTES[accent] : PALETTES[mode]).map(color => new THREE.Color(color)), [mode, accent])

  useEffect(() => {
    if (reducedMotion) {
      uniforms.uBody.value.copy(targetColors[0])
      uniforms.uLight.value.copy(targetColors[1])
      uniforms.uPearl.value.copy(targetColors[2])
      uniforms.uActivity.value = mode === 'thinking' ? 1 : mode === 'idle' ? 0 : 0.35
      uniforms.uAmplitude.value = 0
    }
    invalidate()
  }, [reducedMotion, mode, targetColors, uniforms, invalidate])

  useFrame((_, frameDelta) => {
    if (!mesh.current) return
    const delta = Math.min(frameDelta, 0.05)
    const smoothing = 1 - Math.exp(-delta * 5)
    const voiceActive = mode === 'listening' || mode === 'speaking'
    const targetVolume = voiceActive && Number.isFinite(audioLevel) ? THREE.MathUtils.clamp(audioLevel, 0, 1) : 0
    amplitude.current = THREE.MathUtils.damp(amplitude.current, targetVolume, targetVolume > amplitude.current ? 11 : 5, delta)
    const activity = mode === 'thinking' ? 1 : mode === 'idle' ? 0 : 0.35
    uniforms.uActivity.value = THREE.MathUtils.damp(uniforms.uActivity.value, activity, 3, delta)
    uniforms.uBody.value.lerp(targetColors[0], smoothing)
    uniforms.uLight.value.lerp(targetColors[1], smoothing)
    uniforms.uPearl.value.lerp(targetColors[2], smoothing)
    uniforms.uAmplitude.value = reducedMotion ? 0 : amplitude.current

    if (reducedMotion) {
      mesh.current.rotation.set(0.1, 0, -0.12)
      mesh.current.position.set(0, 0, 0)
      mesh.current.scale.setScalar(1)
      return
    }

    motionTime.current += delta
    const time = motionTime.current
    uniforms.uTime.value = time
    const breath = Math.sin(time * 0.85) * 0.006
    const targetScale = 1 + breath + amplitude.current * (mode === 'speaking' ? 0.048 : 0.023)
    mesh.current.scale.setScalar(THREE.MathUtils.damp(mesh.current.scale.x, targetScale, 6, delta))
    mesh.current.position.y = THREE.MathUtils.damp(mesh.current.position.y, Math.sin(time * 0.62) * 0.028, 3, delta)
    mesh.current.rotation.x = THREE.MathUtils.damp(mesh.current.rotation.x, 0.12 + pointer.current.y * 0.15, 3, delta)
    mesh.current.rotation.y = THREE.MathUtils.damp(mesh.current.rotation.y, Math.sin(time * 0.18) * 0.13 + pointer.current.x * 0.25, 3, delta)
    mesh.current.rotation.z = THREE.MathUtils.damp(mesh.current.rotation.z, -0.12 + Math.sin(time * 0.21) * 0.018, 3, delta)
  })

  return (
    <mesh ref={mesh} rotation={[0.12, 0, -0.12]}>
      <sphereGeometry args={[1.08, quality === 'low' ? 48 : 80, quality === 'low' ? 32 : 64]} />
      <shaderMaterial vertexShader={vertexShader} fragmentShader={fragmentShader} uniforms={uniforms} transparent />
    </mesh>
  )
}

class OrbBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

function FallbackSphere() {
  return <span className="soul-orb__fallback" />
}

function ContextWatcher({ onLost }: { onLost: () => void }) {
  const gl = useThree(state => state.gl)
  useEffect(() => {
    const canvas = gl.domElement
    canvas.addEventListener('webglcontextlost', onLost)
    return () => canvas.removeEventListener('webglcontextlost', onLost)
  }, [gl, onLost])
  return null
}

function hasWebGL() {
  try {
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('webgl2')
    if (!context) return false
    context.getExtension('WEBGL_lose_context')?.loseContext()
    return true
  } catch { return false }
}

/** A self-contained, gently reactive 3D orb without external textures or network assets. */
export function Orb({ mode, audioLevel, reducedMotion = false, quality = 'auto', accent = 'cyan' }: OrbProps) {
  const pointer = useRef({ x: 0, y: 0 })
  const [webgl, setWebgl] = useState(hasWebGL)
  const [visible, setVisible] = useState(() => !document.hidden)
  const [systemReducedMotion, setSystemReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const still = reducedMotion || systemReducedMotion

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const updateMotion = () => setSystemReducedMotion(media.matches)
    const updateVisibility = () => setVisible(!document.hidden)
    media.addEventListener('change', updateMotion)
    document.addEventListener('visibilitychange', updateVisibility)
    return () => {
      media.removeEventListener('change', updateMotion)
      document.removeEventListener('visibilitychange', updateVisibility)
    }
  }, [])

  return (
    <div
      className={`soul-orb soul-orb--${mode}${still ? ' soul-orb--still' : ''}`}
      aria-hidden="true"
      onPointerMove={event => {
        const bounds = event.currentTarget.getBoundingClientRect()
        pointer.current.x = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2
        pointer.current.y = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2
      }}
      onPointerLeave={() => { pointer.current = { x: 0, y: 0 } }}
    >
      <div className="soul-orb__aura" />
      <div className="soul-orb__shadow" />
      <div className="soul-orb__surface">
        {webgl ? (
          <OrbBoundary fallback={<FallbackSphere />}>
            <Suspense fallback={<FallbackSphere />}>
              <Canvas
                camera={{ position: [0, 0, 4.4], fov: 38 }}
                dpr={quality === 'low' ? 1 : [1, 1.5]}
                frameloop={still || !visible ? 'demand' : 'always'}
                gl={{ alpha: true, antialias: true, powerPreference: 'low-power' }}
                onCreated={({ gl }) => {
                  gl.setClearColor(0x000000, 0)
                  gl.toneMapping = THREE.ACESFilmicToneMapping
                  gl.toneMappingExposure = 1.16
                }}
              >
                <ContextWatcher onLost={() => setWebgl(false)} />
                <GlassSphere mode={mode} audioLevel={audioLevel} reducedMotion={still} quality={quality} accent={accent} pointer={pointer} />
              </Canvas>
            </Suspense>
          </OrbBoundary>
        ) : <FallbackSphere />}
      </div>
      <span className="soul-orb__state-ring" />
    </div>
  )
}

export default Orb
