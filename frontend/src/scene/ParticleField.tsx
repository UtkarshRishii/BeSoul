import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useUIStore } from '../state/uiState'

const PARTICLE_COUNT_LOW = 4000
const PARTICLE_COUNT_MED = 8000
const PARTICLE_COUNT_HIGH = 14000

interface ParticleFieldProps {
  quality: 'auto' | 'low' | 'high'
  amplitude: number
}

/* ─── Galactic Starfield Accretion Disk (1:1 with ref.mp4) ─── */
export function ParticleField({ quality, amplitude }: ParticleFieldProps) {
  const pointsRef = useRef<THREE.Points>(null)
  const visualState = useUIStore(s => s.visualState)

  const count =
    quality === 'low'
      ? PARTICLE_COUNT_LOW
      : quality === 'high'
      ? PARTICLE_COUNT_HIGH
      : PARTICLE_COUNT_MED

  // Generate galactic disk & cosmic halo coordinates
  const { initialData, colors, sizes } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const colors = new Float32Array(count * 3)
    const sizes = new Float32Array(count)

    // Store polar coordinates for fast Keplerian orbit calculation:
    // [radius, angle, yOffset, orbitalSpeed, isHalo]
    const initialData = new Float32Array(count * 5)

    for (let i = 0; i < count; i++) {
      const i3 = i * 3
      const i5 = i * 5
      const isHalo = Math.random() < 0.15

      let r: number
      let theta: number = Math.random() * Math.PI * 2
      let y: number
      let speed: number

      if (!isHalo) {
        // Galactic accretion disc (85% of particles)
        // Distribution: dense near core (r=0.6), spreading outward to r=4.2
        r = 0.55 + Math.pow(Math.random(), 0.55) * 3.8
        y = (Math.random() - 0.5) * 0.35 * Math.pow(r / 2.0, 0.7)
        // Keplerian speed: inner stars orbit faster
        speed = (0.28 / Math.sqrt(r)) * (0.8 + Math.random() * 0.4)
      } else {
        // Outer spherical star halo (15% of particles)
        r = 1.0 + Math.pow(Math.random(), 0.7) * 4.8
        const phi = Math.acos(2 * Math.random() - 1)
        theta = Math.random() * Math.PI * 2
        y = r * Math.cos(phi) * 0.6
        speed = 0.05 * (Math.random() - 0.5)
      }

      initialData[i5] = r
      initialData[i5 + 1] = theta
      initialData[i5 + 2] = y
      initialData[i5 + 3] = speed
      initialData[i5 + 4] = isHalo ? 1 : 0

      // Initial Cartesian position
      positions[i3] = r * Math.cos(theta)
      positions[i3 + 1] = y
      positions[i3 + 2] = r * Math.sin(theta)

      // Particle Colors: White near core -> Cyan -> Sapphire Blue
      const colorRatio = Math.min(1, Math.max(0, (r - 0.6) / 3.4))
      if (colorRatio < 0.2) {
        // Core white-cyan
        colors[i3] = 0.95 + Math.random() * 0.05
        colors[i3 + 1] = 0.98 + Math.random() * 0.02
        colors[i3 + 2] = 1.0
      } else if (colorRatio < 0.6) {
        // Electric Cyan / Sky Blue
        colors[i3] = 0.15 + Math.random() * 0.2
        colors[i3 + 1] = 0.8 + Math.random() * 0.2
        colors[i3 + 2] = 1.0
      } else {
        // Deep Cosmic Blue / Indigo
        colors[i3] = 0.08 + Math.random() * 0.15
        colors[i3 + 1] = 0.45 + Math.random() * 0.25
        colors[i3 + 2] = 0.95
      }

      // Sizes: stars vary in magnitude
      sizes[i] = 0.8 + Math.random() * 2.4
    }

    return { initialData, colors, sizes, positions }
  }, [count])

  useFrame(({ clock }, delta) => {
    if (!pointsRef.current) return
    const dt = Math.min(delta, 0.05)
    const time = clock.elapsedTime
    const geo = pointsRef.current.geometry
    const pos = geo.attributes.position.array as Float32Array

    // Global speed multiplier based on state
    const stateSpeed =
      visualState === 'thinking' ? 1.8 : visualState === 'speaking' ? 1.4 : visualState === 'acting' ? 2.0 : 1.0
    const ampBoost = visualState === 'speaking' || visualState === 'listening' ? amplitude * 0.35 : 0

    // Radial wave phase for speech ripple
    const ripplePhase = (time * 2.5) % 4.5

    for (let i = 0; i < count; i++) {
      const i3 = i * 3
      const i5 = i * 5

      const r = initialData[i5]
      let theta = initialData[i5 + 1]
      const yBase = initialData[i5 + 2]
      const speed = initialData[i5 + 3]
      const isHalo = initialData[i5 + 4] === 1

      // Advance orbital angle
      theta += speed * stateSpeed * dt
      initialData[i5 + 1] = theta

      // Acoustic wave ripple reaction
      let rOffset = 0
      let yOffset = 0
      if (!isHalo && ampBoost > 0) {
        const distFromWave = Math.abs(r - ripplePhase)
        if (distFromWave < 0.5) {
          const waveIntensity = (1 - distFromWave / 0.5) * ampBoost
          rOffset = waveIntensity * 0.2
          yOffset = Math.sin(time * 8 + r * 5) * waveIntensity * 0.18
        }
      }

      const activeR = r + rOffset
      pos[i3] = activeR * Math.cos(theta)
      pos[i3 + 1] = yBase + yOffset + Math.sin(time * 0.5 + theta * 2) * 0.04
      pos[i3 + 2] = activeR * Math.sin(theta)
    }

    geo.attributes.position.needsUpdate = true

    // Subtle galactic tilt sway
    pointsRef.current.rotation.y = time * 0.02
    pointsRef.current.rotation.z = Math.sin(time * 0.3) * 0.03
  })

  return (
    // Tilt the galactic disk slightly toward the camera (just like in ref.mp4)
    <group rotation={[0.35, 0, -0.05]}>
      <points ref={pointsRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[new Float32Array(count * 3), 3]}
          />
          <bufferAttribute
            attach="attributes-color"
            args={[colors, 3]}
          />
          <bufferAttribute
            attach="attributes-size"
            args={[sizes, 1]}
          />
        </bufferGeometry>
        <pointsMaterial
          size={quality === 'low' ? 0.028 : 0.022}
          vertexColors
          transparent
          opacity={0.85}
          sizeAttenuation
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  )
}

/* ─── Neural Connections & Orbital Fragments (retained for clean scene assembly) ─── */
export function NeuralConnections({ quality: _quality }: { quality: 'auto' | 'low' | 'high' }) {
  return null
}

export function OrbitalFragments() {
  return null
}
