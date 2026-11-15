import { useEffect, useRef, useState } from 'react'
import maplibregl, { type ImageSource, type Map as MlMap, type StyleSpecification } from 'maplibre-gl'
import type { Corners } from './types'

interface Props {
  corners: Corners
  /** Imagem do lado esquerdo do slider (optico). */
  opticalUrl: string
  /** Imagem de radar em tons de cinza (HH ou HV). */
  baseUrl: string
  /** Camada colorida por cima do radar (classes ou mudanca), ou null. */
  overlayUrl: string | null
  compare: boolean
  /** Posicao do slider, de 0 (tudo radar) a 1 (tudo optico). */
  split: number
  onSplit: (v: number) => void
  leftLabel: string
  rightLabel: string
  /** Ponto marcado no mapa (clique), ou null. */
  marker: [number, number] | null
  onPick: (lngLat: [number, number]) => void
}

// Estilo minimo e local: fundo liso + OpenStreetMap esmaecido. Sem internet, os tiles do OSM
// simplesmente nao aparecem e o resto continua funcionando.
const style: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#07162B' } },
    { id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-opacity': 0.3, 'raster-saturation': -0.7 } },
  ],
}

function createMap(container: HTMLElement, corners: Corners): MlMap {
  const lons = corners.map((c) => c[0])
  const lats = corners.map((c) => c[1])
  const w = Math.min(...lons), e = Math.max(...lons), s = Math.min(...lats), n = Math.max(...lats)
  const pad = 0.35
  const map = new maplibregl.Map({
    container,
    style,
    bounds: [[w, s], [e, n]],
    fitBoundsOptions: { padding: 16 },
    maxBounds: [[w - pad, s - pad], [e + pad, n + pad]],
    maxZoom: 13.5,
    dragRotate: false,
    pitchWithRotate: false,
    attributionControl: false,
  })
  map.touchZoomRotate.disableRotation()
  return map
}

export default function CompareMap(p: Props) {
  const wrap = useRef<HTMLDivElement>(null)
  const leftEl = useRef<HTMLDivElement>(null)
  const rightEl = useRef<HTMLDivElement>(null)
  const maps = useRef<{ left: MlMap; right: MlMap } | null>(null)
  const [ready, setReady] = useState(false)
  // URLs que estao no mapa neste momento.
  const shown = useRef({ base: '', overlay: '' })
  // Valores mais recentes para o callback de "load", que roda uma vez so.
  const latest = useRef(p)
  latest.current = p

  useEffect(() => {
    const left = createMap(leftEl.current!, p.corners)
    const right = createMap(rightEl.current!, p.corners)
    right.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')
    maps.current = { left, right }

    // Mantem os dois mapas na mesma posicao.
    let syncing = false
    const follow = (from: MlMap, to: MlMap) => () => {
      if (syncing) return
      syncing = true
      to.jumpTo({ center: from.getCenter(), zoom: from.getZoom() })
      syncing = false
    }
    left.on('move', follow(left, right))
    right.on('move', follow(right, left))
    for (const m of [left, right]) {
      m.on('click', (e) => latest.current.onPick([e.lngLat.lng, e.lngLat.lat]))
      m.getCanvas().style.cursor = 'crosshair'
    }

    let loaded = 0
    const done = () => { if (++loaded === 2) setReady(true) }
    left.on('load', () => {
      left.addSource('optical', { type: 'image', url: latest.current.opticalUrl, coordinates: p.corners })
      left.addLayer({ id: 'optical', type: 'raster', source: 'optical', paint: { 'raster-fade-duration': 0 } })
      done()
    })
    right.on('load', () => {
      const cur = latest.current
      shown.current = { base: cur.baseUrl, overlay: cur.overlayUrl ?? cur.baseUrl }
      right.addSource('base', { type: 'image', url: cur.baseUrl, coordinates: p.corners })
      right.addLayer({ id: 'base', type: 'raster', source: 'base', paint: { 'raster-fade-duration': 0 } })
      right.addSource('overlay', { type: 'image', url: cur.overlayUrl ?? cur.baseUrl, coordinates: p.corners })
      right.addLayer({
        id: 'overlay', type: 'raster', source: 'overlay',
        layout: { visibility: cur.overlayUrl ? 'visible' : 'none' },
        paint: { 'raster-fade-duration': 0, 'raster-resampling': 'nearest', 'raster-opacity': 0.92 },
      })
      done()
    })

    const ro = new ResizeObserver(() => { left.resize(); right.resize() })
    ro.observe(wrap.current!)
    return () => { ro.disconnect(); left.remove(); right.remove(); maps.current = null; setReady(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!ready || !maps.current) return
    const { right } = maps.current
    // So troca a imagem quando a URL muda: trocas repetidas cancelam o carregamento anterior.
    if (shown.current.base !== p.baseUrl) {
      shown.current.base = p.baseUrl
      ;(right.getSource('base') as ImageSource).updateImage({ url: p.baseUrl, coordinates: p.corners })
    }
    if (p.overlayUrl && shown.current.overlay !== p.overlayUrl) {
      shown.current.overlay = p.overlayUrl
      ;(right.getSource('overlay') as ImageSource).updateImage({ url: p.overlayUrl, coordinates: p.corners })
    }
    right.setLayoutProperty('overlay', 'visibility', p.overlayUrl ? 'visible' : 'none')
  }, [ready, p.baseUrl, p.overlayUrl, p.corners])

  // Marcador do ponto clicado, nos dois mapas (cada lado do slider mostra o seu).
  useEffect(() => {
    if (!ready || !maps.current || !p.marker) return
    const made = [maps.current.left, maps.current.right].map((m) => {
      const el = document.createElement('div')
      el.className = 'cmp-pin'
      return new maplibregl.Marker({ element: el }).setLngLat(p.marker!).addTo(m)
    })
    return () => made.forEach((m) => m.remove())
  }, [ready, p.marker])

  // Arrastar a divisoria (mouse, toque ou teclado).
  const drag = (ev: React.PointerEvent) => {
    ev.preventDefault()
    const el = ev.currentTarget as HTMLElement
    el.setPointerCapture(ev.pointerId)
    const move = (e: PointerEvent) => {
      const r = wrap.current!.getBoundingClientRect()
      p.onSplit(Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)))
    }
    const up = () => { el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up) }
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerup', up)
  }
  const key = (ev: React.KeyboardEvent) => {
    if (ev.key === 'ArrowLeft') p.onSplit(Math.max(0, p.split - 0.05))
    if (ev.key === 'ArrowRight') p.onSplit(Math.min(1, p.split + 0.05))
  }

  const split = p.compare ? p.split : 0
  return (
    <div className="cmp" ref={wrap}>
      <div className="cmp-map" ref={leftEl} />
      <div className="cmp-map" ref={rightEl} style={{ clipPath: `inset(0 0 0 ${split * 100}%)` }} />
      {p.compare && split > 0.12 && <div className="cmp-tag cmp-tag-left">{p.leftLabel}</div>}
      {split < 0.78 && <div className="cmp-tag cmp-tag-right">{p.rightLabel}</div>}
      {p.compare && (
        <div
          className="cmp-handle"
          style={{ left: `${split * 100}%` }}
          role="slider"
          tabIndex={0}
          aria-label={`${p.leftLabel} / ${p.rightLabel}`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(split * 100)}
          onPointerDown={drag}
          onKeyDown={key}
        >
          <span className="cmp-grip" aria-hidden="true">‹ ›</span>
        </div>
      )}
    </div>
  )
}
