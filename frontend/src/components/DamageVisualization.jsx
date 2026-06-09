import React, { useEffect, useRef, useState } from 'react'

/**
 * Renders a car-damage image with Azure-CV bounding boxes overlaid on a
 * <canvas>. Bounding boxes use {x, y, w, h} in the image's pixel space —
 * exactly what Azure Image Analysis 4.0 returns.
 */
export default function DamageVisualization({ imageUrl, regions }) {
  const imgRef = useRef(null)
  const canvasRef = useRef(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!loaded) return
    const img = imgRef.current
    const canvas = canvasRef.current
    if (!img || !canvas) return

    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (!regions || regions.length === 0) return

    regions.forEach((r, i) => {
      const { bbox, label, confidence } = r
      if (!bbox) return
      const color = pickColor(i)
      ctx.lineWidth = Math.max(3, img.naturalWidth / 400)
      ctx.strokeStyle = color
      ctx.fillStyle = color
      ctx.strokeRect(bbox.x, bbox.y, bbox.w, bbox.h)
      // Label background
      const text = `${label}${confidence ? `  ${(confidence * 100).toFixed(0)}%` : ''}`
      ctx.font = `${Math.max(14, img.naturalWidth / 70)}px system-ui, sans-serif`
      const pad = 6
      const tw = ctx.measureText(text).width + pad * 2
      const th = parseInt(ctx.font, 10) + pad
      ctx.fillRect(bbox.x, Math.max(0, bbox.y - th), tw, th)
      ctx.fillStyle = '#fff'
      ctx.fillText(text, bbox.x + pad, Math.max(th - pad / 2, bbox.y - pad / 2))
    })
  }, [loaded, regions, imageUrl])

  return (
    <div className="damage-canvas-wrap">
      <img ref={imgRef} src={imageUrl} alt="claim" onLoad={() => setLoaded(true)} />
      <canvas ref={canvasRef} />
    </div>
  )
}

function pickColor(i) {
  const palette = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#ec4899']
  return palette[i % palette.length]
}
