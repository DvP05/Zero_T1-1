/**
 * Generates an animated pulsing dot for Mapbox symbol layers.
 */
export function createPulseDot(size = 128, map, color = 'rgba(244, 63, 94,') {
  return {
    width: size,
    height: size,
    data: new Uint8ClampedArray(size * size * 4),

    onAdd() {},

    render() {
      const duration = 1200
      const t = (performance.now() % duration) / duration
      const radius = (size / 2) * (0.3 + 0.55 * t)
      const context = document.createElement('canvas').getContext('2d')
      const canvas = context.canvas
      canvas.width = size
      canvas.height = size

      // Draw outer pulsing halo
      context.clearRect(0, 0, size, size)
      context.beginPath()
      context.arc(size / 2, size / 2, radius, 0, Math.PI * 2)
      context.fillStyle = `${color} ${1 - t})`
      context.fill()

      // Draw middle ring
      context.beginPath()
      context.arc(size / 2, size / 2, size / 4, 0, Math.PI * 2)
      context.fillStyle = `${color} 0.65)`
      context.strokeStyle = '#ffffff'
      context.lineWidth = 2
      context.fill()
      context.stroke()

      // Draw center core
      context.beginPath()
      context.arc(size / 2, size / 2, size / 8, 0, Math.PI * 2)
      context.fillStyle = '#ffffff'
      context.fill()

      this.data = context.getImageData(0, 0, size, size).data

      if (map) {
        map.triggerRepaint()
      }

      return true
    },
  }
}

/**
 * Generates high-DPI circular badge icon for emergency facilities.
 */
export function createFacilityBadge(symbol, bgColor, size = 64) {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')

  // Smooth circular badge with border
  ctx.beginPath()
  ctx.arc(size / 2, size / 2, size / 2 - 3, 0, Math.PI * 2)
  ctx.fillStyle = bgColor
  ctx.fill()
  ctx.lineWidth = 3.5
  ctx.strokeStyle = '#ffffff'
  ctx.stroke()

  // Center symbol / emoji
  ctx.font = '28px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(symbol, size / 2, size / 2 + 1)

  return ctx.getImageData(0, 0, size, size)
}

/**
 * Generates high-DPI marine buoy beacon badge.
 */
export function createBuoyBadge(isAnomalous = false, size = 64) {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')

  // Moored marine buoy badge
  ctx.beginPath()
  ctx.arc(size / 2, size / 2, size / 2 - 3, 0, Math.PI * 2)
  ctx.fillStyle = isAnomalous ? '#f43f5e' : '#0284c7'
  ctx.fill()
  ctx.lineWidth = 3.5
  ctx.strokeStyle = '#ffffff'
  ctx.stroke()

  // Center marine anchor symbol
  ctx.font = '28px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('⚓', size / 2, size / 2 + 1)

  return ctx.getImageData(0, 0, size, size)
}
