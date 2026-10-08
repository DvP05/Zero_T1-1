/**
 * Generates an animated pulsing dot for Mapbox symbol layers.
 */
export function createPulseDot(size = 128, map) {
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
      context.fillStyle = `rgba(251, 113, 133, ${1 - t})`
      context.fill()

      // Draw middle ring
      context.beginPath()
      context.arc(size / 2, size / 2, size / 4, 0, Math.PI * 2)
      context.fillStyle = 'rgba(251, 113, 133, 0.6)'
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
