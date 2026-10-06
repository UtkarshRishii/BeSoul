import { Component, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { SoulState } from './types'

interface EntityProps { state: SoulState; amplitude: number; reducedMotion: boolean; quality: 'auto' | 'low' | 'high' }
const semanticColors: Partial<Record<SoulState, string>> = {
  ERROR: '#d7aa83', INTERRUPTED: '#a8b4be', WAITING_CONFIRMATION: '#e2cda6', SEEING: '#a2d5ee',
}

function ribbonGeometry(phase: number, detail: number) {
  const positions: number[] = [], indices: number[] = []
  for (let i = 0; i <= detail; i++) {
    const t = i / detail, shape = Math.pow(Math.sin(Math.PI * t), .8)
    for (let side = 0; side < 2; side++) {
      const angle = phase + t * 2.15 + (side - .5) * (.14 + .63 * shape)
      const radius = .10 + 1.02 * shape + side * .06
      positions.push(Math.cos(angle) * radius, (t - .5) * 2.72, Math.sin(angle) * radius)
    }
    if (i < detail) { const a = i * 2; indices.push(a, a + 1, a + 2, a + 1, a + 3, a + 2) }
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setIndex(indices)
  geometry.computeVertexNormals()
  return geometry
}

function Filaments({ state, amplitude, reducedMotion, quality }: EntityProps) {
  const group = useRef<THREE.Group>(null)
  const particles = useRef<THREE.Points>(null)
  const layers = useRef<(THREE.Mesh | null)[]>([])
  const accent = semanticColors[state] || '#b7f4dc'
  const details = quality === 'low' ? 24 : 58
  const ribbons = useMemo(() => Array.from({ length: 7 }, (_, i) => ribbonGeometry(i * Math.PI * 2 / 7, details)), [details])
  const particlePositions = useMemo(() => {
    const count = quality === 'low' ? 180 : 620
    const positions = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const t = i / count
      const angle = t * Math.PI * 24 + Math.sin(i * 12.17) * .15
      const radius = .35 + Math.sin(Math.PI * t) * .80
      positions[i * 3] = Math.cos(angle) * radius
      positions[i * 3 + 1] = (t - .5) * 2.55
      positions[i * 3 + 2] = Math.sin(angle) * radius
    }
    return positions
  }, [quality])
  useEffect(() => () => ribbons.forEach(geometry => geometry.dispose()), [ribbons])

  useFrame(({ clock }, delta) => {
    if (!group.current || reducedMotion) return
    const dt = Math.min(delta, .05), time = clock.elapsedTime
    const focused = ['THINKING', 'ACTING', 'VERIFYING'].includes(state)
    const perception = state === 'SEEING'
    const listening = state === 'LISTENING'
    // Only real PCM/microphone levels create rhythmic speaking/listening motion.
    const audioScale = state === 'SPEAKING' || listening ? amplitude * .15 : 0
    const breathing = state === 'SPEAKING' ? 0 : Math.sin(time * .65) * .009
    const scale = state === 'VERIFYING' ? .91 : listening ? 1.065 : perception ? 1.035 : 1
    group.current.scale.lerp(new THREE.Vector3(scale + breathing + audioScale, 1 + audioScale * .65, scale + audioScale), dt * 3)
    group.current.rotation.y += dt * (focused ? .11 : .028)
    group.current.rotation.z = THREE.MathUtils.damp(group.current.rotation.z, perception ? .16 : state === 'ACTING' ? -.11 : -.035, 2, dt)
    layers.current.forEach((layer, i) => {
      if (!layer) return
      layer.rotation.y += dt * (state === 'THINKING' ? .025 * (i % 2 ? 1 : -1) : .002)
      layer.position.y = THREE.MathUtils.damp(layer.position.y, listening ? (i % 2 ? .04 : -.04) : 0, 2, dt)
    })
    if (particles.current) particles.current.rotation.y -= dt * (focused ? .075 : .011)
  })

  return <group ref={group} rotation={[.09, -.35, -.035]}>
    {ribbons.map((geometry, i) => <mesh key={i} geometry={geometry} ref={mesh => { layers.current[i] = mesh }}>
      <meshPhysicalMaterial color={i % 2 ? '#72968e' : accent} emissive={accent} emissiveIntensity={.07}
        transparent opacity={.23 + i % 3 * .055} roughness={.22} metalness={.35}
        side={THREE.DoubleSide} depthWrite={false} clearcoat={.65} />
    </mesh>)}
    <points ref={particles}>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[particlePositions, 3]} /></bufferGeometry>
      <pointsMaterial color={accent} size={quality === 'low' ? .014 : .011} transparent opacity={.7}
        sizeAttenuation depthWrite={false} blending={THREE.AdditiveBlending} />
    </points>
    <mesh rotation={[.28, .32, .68]} scale={[.2, .36, .2]}>
      <octahedronGeometry args={[1, 0]} />
      <meshPhysicalMaterial color="#d5fff0" roughness={.2} metalness={.4} transparent opacity={.62} />
    </mesh>
    <group rotation={[Math.PI / 2.15, .14, -.2]}>
      <mesh><torusGeometry args={[1.42, .004, 6, 96, Math.PI * 1.35]} /><meshBasicMaterial color={accent} transparent opacity={.30} /></mesh>
      <mesh rotation={[0, 0, Math.PI * 1.3]} scale={.92}>
        <torusGeometry args={[1.42, .002, 4, 96, Math.PI * .9]} /><meshBasicMaterial color="#93b1aa" transparent opacity={.30} />
      </mesh>
    </group>
  </group>
}

function StaticEntity({ state }: { state: SoulState }) {
  return <svg className="entity-fallback" viewBox="0 0 340 360" role="img" aria-label={`SOUL in ${state.toLowerCase()} state`}>
    <defs>
      <linearGradient id="filament" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#a6dbc5" stopOpacity=".15" /><stop offset=".5" stopColor="#b7f4dc" stopOpacity=".48" /><stop offset="1" stopColor="#87ae9f" stopOpacity=".1" /></linearGradient>
    </defs>
    {[0, 1, 2, 3, 4, 5].map(i => <path key={i} d="M 171 55 C 56 119, 86 248, 170 305 C 266 253, 242 123, 171 55 Z"
      fill="url(#filament)" stroke="#b7f4dc" strokeOpacity=".23" strokeWidth=".6" transform={`rotate(${i * 26 - 65} 170 180) scale(${.8 + i * .035} 1)`} />)}
    <ellipse cx="170" cy="183" rx="137" ry="46" fill="none" stroke="#b7f4dc" strokeOpacity=".22" strokeWidth=".7" transform="rotate(-19 170 180)" />
    <path d="M170 151 185 179 170 211 155 179Z" fill="#b7f4dc" opacity=".72" />
  </svg>
}

class SceneBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

export default function Entity(props: EntityProps) {
  const [supported, setSupported] = useState(() => {
    try { const canvas = document.createElement('canvas'); return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl')) }
    catch { return false }
  })
  const low = props.quality === 'low'
  return <div className={`entity entity-${props.state.toLowerCase()}`} aria-hidden="true">
    <div className="entity-halo" />
    {supported ? <SceneBoundary fallback={<StaticEntity state={props.state} />}>
      <Canvas camera={{ position: [0, .1, 5.6], fov: 40 }} dpr={low ? 1 : [1, 1.5]}
        frameloop={props.reducedMotion ? 'demand' : 'always'} gl={{ antialias: !low, alpha: true, powerPreference: 'low-power' }}
        onCreated={({ gl }) => gl.domElement.addEventListener('webglcontextlost', () => setSupported(false), { once: true })}>
        <ambientLight intensity={.9} />
        <directionalLight position={[3, 5, 4]} intensity={2.3} color="#c5f7e8" />
        <pointLight position={[-3, -.7, 2]} intensity={9} color="#69849c" />
        <Filaments {...props} />
      </Canvas>
    </SceneBoundary> : <StaticEntity state={props.state} />}
  </div>
}
