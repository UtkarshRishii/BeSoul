import { Component, Suspense, useRef, type ReactNode } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { SoulCore, SoulShell, SoulOuterShell } from './SoulCore'
import { ParticleField, NeuralConnections, OrbitalFragments } from './ParticleField'
import { AtmosphericDust, SoulLighting } from './Environment'
import { useUIStore, getVisualConfig } from '../state/uiState'

interface SoulSceneProps {
  amplitude: number
  quality: 'auto' | 'low' | 'high'
  reducedMotion: boolean
}

/* ─── Camera Controller ─── */
function CameraController() {
  const mouseX = useUIStore(s => s.mouseX)
  const mouseY = useUIStore(s => s.mouseY)
  const visualState = useUIStore(s => s.visualState)
  const overlay = useUIStore(s => s.overlay)

  useFrame(({ camera }, delta) => {
    const dt = Math.min(delta, 0.05)

    // Subtle parallax from mouse
    const parallaxX = (mouseX - 0.5) * 0.3
    const parallaxY = (mouseY - 0.5) * -0.15

    // SOUL position adjustment for overlays
    let targetX = parallaxX
    let targetY = 0.15 + parallaxY
    const targetZ = 5.2

    if (overlay === 'settings') {
      targetX = -1.2 + parallaxX * 0.5
    } else if (overlay === 'activity') {
      targetX = -0.5 + parallaxX * 0.5
    }

    camera.position.x += (targetX - camera.position.x) * dt * 2.5
    camera.position.y += (targetY - camera.position.y) * dt * 2.5
    camera.position.z += (targetZ - camera.position.z) * dt * 2.5

    camera.lookAt(0, 0, 0)
  })

  return null
}

/* ─── Main Entity Group with state transforms ─── */
function EntityGroup({ amplitude }: { amplitude: number }) {
  const groupRef = useRef<THREE.Group>(null)
  const visualState = useUIStore(s => s.visualState)
  const config = getVisualConfig(visualState)

  useFrame(({ clock }, delta) => {
    if (!groupRef.current) return
    const dt = Math.min(delta, 0.05)
    const time = clock.elapsedTime

    // Slow overall rotation
    groupRef.current.rotation.y += dt * config.rotationSpeed

    // Subtle tilt based on state
    let targetTiltZ = -0.03
    if (visualState === 'seeing') targetTiltZ = 0.12
    if (visualState === 'acting') targetTiltZ = -0.08
    if (visualState === 'listening') targetTiltZ = 0.05

    groupRef.current.rotation.z += (targetTiltZ - groupRef.current.rotation.z) * dt * 2

    // Overall scale
    const targetScale = config.coreScale
    const s = groupRef.current.scale.x
    const newScale = s + (targetScale - s) * dt * 3
    groupRef.current.scale.setScalar(newScale)
  })

  return (
    <group ref={groupRef} position={[0, 0.08, 0]}>
      <SoulCore amplitude={amplitude} />
      <SoulShell />
      <SoulOuterShell />
    </group>
  )
}

/* ─── Error Boundary ─── */
class SceneBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

/* ─── Static Fallback ─── */
function StaticFallback() {
  return (
    <div className="soul-fallback">
      <svg viewBox="0 0 200 200" width="120" height="120">
        <defs>
          <radialGradient id="soulGlow" cx="50%" cy="50%">
            <stop offset="0%" stopColor="#EAFBF8" stopOpacity="0.8" />
            <stop offset="50%" stopColor="#8FE3D3" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#050809" stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx="100" cy="100" r="80" fill="url(#soulGlow)" />
        <circle cx="100" cy="100" r="20" fill="#EAFBF8" opacity="0.6" />
      </svg>
    </div>
  )
}

/* ─── Main Scene Export ─── */
export default function SoulScene({ amplitude, quality, reducedMotion }: SoulSceneProps) {
  const low = quality === 'low'

  return (
    <div className="soul-scene" aria-hidden="true">
      <SceneBoundary fallback={<StaticFallback />}>
        <Suspense fallback={<StaticFallback />}>
          <Canvas
            camera={{ position: [0, 0.15, 5.2], fov: 38 }}
            dpr={low ? 1 : [1, 1.5]}
            frameloop={reducedMotion ? 'demand' : 'always'}
            gl={{
              antialias: !low,
              alpha: true,
              powerPreference: low ? 'low-power' : 'high-performance',
              toneMapping: THREE.ACESFilmicToneMapping,
              toneMappingExposure: 1.2,
            }}
          >
            <CameraController />
            <SoulLighting />
            <EntityGroup amplitude={amplitude} />
            <ParticleField quality={quality} amplitude={amplitude} />
            <NeuralConnections quality={quality} />
            <OrbitalFragments />
            <AtmosphericDust quality={quality} />
          </Canvas>
        </Suspense>
      </SceneBoundary>
    </div>
  )
}
