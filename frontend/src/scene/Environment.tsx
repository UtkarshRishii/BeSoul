import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useUIStore, getVisualConfig } from '../state/uiState'

/* ─── Atmospheric dust particles (background) ─── */
export function AtmosphericDust({ quality }: { quality: 'auto' | 'low' | 'high' }) {
  const pointsRef = useRef<THREE.Points>(null)
  const count = quality === 'low' ? 300 : quality === 'high' ? 1500 : 800

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 20
      arr[i * 3 + 1] = (Math.random() - 0.5) * 14
      arr[i * 3 + 2] = (Math.random() - 0.5) * 12 - 3
    }
    return arr
  }, [count])

  useFrame(({ clock }, delta) => {
    if (!pointsRef.current) return
    const dt = Math.min(delta, 0.05)
    pointsRef.current.rotation.y += dt * 0.003
    pointsRef.current.rotation.x += dt * 0.001
  })

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color="#4A6E63"
        size={0.015}
        transparent
        opacity={0.2}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  )
}

/* ─── Radial light around SOUL ─── */
export function SoulLighting() {
  const visualState = useUIStore(s => s.visualState)
  const config = getVisualConfig(visualState)
  const pointLightRef = useRef<THREE.PointLight>(null)

  useFrame((_, delta) => {
    if (!pointLightRef.current) return
    const dt = Math.min(delta, 0.05)
    const targetIntensity = config.lightIntensity * 8
    pointLightRef.current.intensity += (targetIntensity - pointLightRef.current.intensity) * dt * 3
  })

  return (
    <>
      <ambientLight intensity={0.15} color="#0A1510" />
      <pointLight
        ref={pointLightRef}
        position={[0, 0.2, 1.5]}
        intensity={8}
        color="#B8F5EA"
        distance={12}
        decay={2}
      />
      <pointLight
        position={[-2.5, -0.5, 0.5]}
        intensity={2}
        color="#4A6E63"
        distance={8}
        decay={2}
      />
      <pointLight
        position={[2, 1.5, -1]}
        intensity={1.5}
        color="#2A4A5E"
        distance={6}
        decay={2}
      />
    </>
  )
}

/* ─── Camera rig with parallax ─── */
export function CameraRig() {
  const mouseX = useUIStore(s => s.mouseX)
  const mouseY = useUIStore(s => s.mouseY)
  const groupRef = useRef<THREE.Group>(null)
  const target = useRef({ x: 0, y: 0 })

  useFrame((_, delta) => {
    if (!groupRef.current) return
    const dt = Math.min(delta, 0.05)

    // Very subtle parallax
    target.current.x = (mouseX - 0.5) * 0.15
    target.current.y = (mouseY - 0.5) * -0.08

    groupRef.current.rotation.y += (target.current.x - groupRef.current.rotation.y) * dt * 2
    groupRef.current.rotation.x += (target.current.y - groupRef.current.rotation.x) * dt * 2
  })

  return <group ref={groupRef} />
}
