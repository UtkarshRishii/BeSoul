import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useUIStore, getVisualConfig } from '../state/uiState'

/* ─── Luminous Pulsar Star Core (1:1 with ref.mp4) ─── */
export function SoulCore({ amplitude }: { amplitude: number }) {
  const coreMesh = useRef<THREE.Mesh>(null)
  const coronaMesh = useRef<THREE.Mesh>(null)
  const flareGroup = useRef<THREE.Group>(null)
  const pulseRingsRef = useRef<THREE.Group>(null)

  const visualState = useUIStore(s => s.visualState)
  const config = getVisualConfig(visualState)

  useFrame(({ clock }, delta) => {
    const dt = Math.min(delta, 0.05)
    const time = clock.elapsedTime
    const ampBoost = visualState === 'speaking' || visualState === 'listening' ? amplitude * 0.4 : 0

    // Core pulsing
    if (coreMesh.current) {
      const baseScale = 0.42 * (1 + ampBoost)
      const pulse = 1 + Math.sin(time * 3.5) * 0.04
      coreMesh.current.scale.setScalar(baseScale * pulse)
    }

    // Corona blooming
    if (coronaMesh.current) {
      const coronaScale = 0.95 * (1 + ampBoost * 1.5)
      const breathing = 1 + Math.sin(time * 2.0) * 0.08
      coronaMesh.current.scale.setScalar(coronaScale * breathing)
      coronaMesh.current.rotation.z += dt * 0.2
    }

    // Lens flare diffraction cross rotation
    if (flareGroup.current) {
      flareGroup.current.rotation.z += dt * 0.05
      const flareScale = 1 + ampBoost * 0.6 + Math.sin(time * 2.8) * 0.06
      flareGroup.current.scale.setScalar(flareScale)
    }

    // Outer ripple waves
    if (pulseRingsRef.current) {
      pulseRingsRef.current.children.forEach((child, idx) => {
        const ring = child as THREE.Mesh
        const speed = 1.2
        const ringTime = (time * speed + idx * 0.8) % 2.5
        const ringScale = 0.5 + ringTime * 1.6
        ring.scale.setScalar(ringScale)

        const mat = ring.material as THREE.MeshBasicMaterial
        if (mat) {
          mat.opacity = Math.max(0, (1 - ringTime / 2.5) * (visualState === 'speaking' ? 0.35 : 0.12))
        }
      })
    }
  })

  return (
    <group position={[0, 0, 0]}>
      {/* 1. Ultra-bright white hot core */}
      <mesh ref={coreMesh}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshBasicMaterial color="#FFFFFF" />
      </mesh>

      {/* 2. Electric Cyan / Sky Blue Corona Halo */}
      <mesh ref={coronaMesh}>
        <sphereGeometry args={[1.2, 32, 32]} />
        <meshBasicMaterial
          color="#00F0FF"
          transparent
          opacity={0.7}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.BackSide}
        />
      </mesh>

      {/* 3. Deep sapphire blue atmospheric falloff */}
      <mesh>
        <sphereGeometry args={[1.8, 32, 32]} />
        <meshBasicMaterial
          color="#0066FF"
          transparent
          opacity={0.25}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.BackSide}
        />
      </mesh>

      {/* 4. Stellar Diffraction Flare Spikes */}
      <group ref={flareGroup}>
        {/* Horizontal lens beam */}
        <mesh scale={[3.8, 0.06, 1]}>
          <planeGeometry args={[1, 1]} />
          <meshBasicMaterial
            color="#A5F3FC"
            transparent
            opacity={0.45}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>

        {/* Vertical subtle beam */}
        <mesh scale={[0.06, 2.4, 1]}>
          <planeGeometry args={[1, 1]} />
          <meshBasicMaterial
            color="#A5F3FC"
            transparent
            opacity={0.3}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>

        {/* Diagonal soft glow cross */}
        <mesh rotation={[0, 0, Math.PI / 4]} scale={[2.0, 0.04, 1]}>
          <planeGeometry args={[1, 1]} />
          <meshBasicMaterial
            color="#38BDF8"
            transparent
            opacity={0.25}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
        <mesh rotation={[0, 0, -Math.PI / 4]} scale={[2.0, 0.04, 1]}>
          <planeGeometry args={[1, 1]} />
          <meshBasicMaterial
            color="#38BDF8"
            transparent
            opacity={0.25}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </group>

      {/* 5. Expanding energy shockwave rings */}
      <group ref={pulseRingsRef}>
        {[0, 1, 2].map((i) => (
          <mesh key={i} rotation={[-Math.PI * 0.15, 0, 0]}>
            <ringGeometry args={[0.95, 1.0, 64]} />
            <meshBasicMaterial
              color="#00F0FF"
              transparent
              opacity={0.2}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
              side={THREE.DoubleSide}
            />
          </mesh>
        ))}
      </group>
    </group>
  )
}

/* ─── Compatible shell exports (retained for clean scene imports) ─── */
export function SoulShell() {
  return null
}

export function SoulOuterShell() {
  return null
}
