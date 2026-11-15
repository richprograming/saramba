import { useEffect, useMemo, useState } from 'react'
import CompareMap from './CompareMap'
import LevelChart from './LevelChart'
import PixelChart from './PixelChart'
import { fill, fmtDate, fmtNum, texts } from './i18n'
import type { AppData, Lang, Layer, Probe } from './types'

const DATA = `${import.meta.env.BASE_URL}data/`
const LAYERS: Layer[] = ['hh', 'hv', 'classes', 'duration', 'change']

async function loadData(): Promise<AppData> {
  const get = async (name: string) => {
    const r = await fetch(DATA + name)
    if (!r.ok) throw new Error(name)
    return r
  }
  const [bounds, stats, cota, optico] = await Promise.all(
    ['bounds.json', 'stats.json', 'cota.json', 'optico.json'].map((n) => get(n).then((r) => r.json())))
  const serie = new Uint8Array(await (await get(stats.serie.arquivo)).arrayBuffer())
  return { bounds, stats, cota, optico, serie }
}

/** Serie de HH (dB) na celula que contem o ponto, ou null se o ponto cai fora do recorte. */
function probeAt(data: AppData, lngLat: [number, number]): Probe | null {
  const [tl, tr, , bl] = data.bounds.cantos_lonlat
  // O recorte e um paralelogramo em lon/lat: resolve p = tl + u*(tr - tl) + v*(bl - tl).
  const ax = tr[0] - tl[0], ay = tr[1] - tl[1], bx = bl[0] - tl[0], by = bl[1] - tl[1]
  const px = lngLat[0] - tl[0], py = lngLat[1] - tl[1]
  const det = ax * by - ay * bx
  const u = (px * by - py * bx) / det, v = (ax * py - ay * px) / det
  const s = data.stats.serie
  const col = Math.floor((u * data.bounds.largura) / s.fator), row = Math.floor((v * data.bounds.altura) / s.fator)
  if (u < 0 || v < 0 || col >= s.largura || row >= s.altura) return null
  const db = data.stats.datas.map((_, i) => {
    const b = data.serie[i * s.largura * s.altura + row * s.largura + col]
    return b === 0 ? null : s.db_min + ((b - 1) / 254) * (s.db_max - s.db_min)
  })
  return { lngLat, db }
}

/** O que cada cartao do modo historia mostra no mapa. */
const STORY: { layer: Layer; date: 'first' | 'last'; compare: boolean; split: number }[] = [
  { layer: 'hh', date: 'first', compare: true, split: 0.9 },
  { layer: 'hh', date: 'first', compare: true, split: 0.1 },
  { layer: 'change', date: 'last', compare: false, split: 0.5 },
  { layer: 'duration', date: 'last', compare: false, split: 0.5 },
]

export default function App() {
  const [data, setData] = useState<AppData | null>(null)
  const [failed, setFailed] = useState(false)
  const [lang, setLang] = useState<Lang>('en')
  const [dateIdx, setDateIdx] = useState(0)
  const [layer, setLayer] = useState<Layer>('hh')
  const [compare, setCompare] = useState(true)
  const [split, setSplit] = useState(0.5)
  const [playing, setPlaying] = useState(false)
  const [story, setStory] = useState<number | null>(null)
  const [probe, setProbe] = useState<Probe | null>(null)
  const [open, setOpen] = useState(false) // gaveta do painel no celular
  const t = texts[lang]

  useEffect(() => { loadData().then(setData).catch(() => setFailed(true)) }, [])
  useEffect(() => { document.documentElement.lang = lang === 'pt' ? 'pt-BR' : 'en' }, [lang])

  const dates = useMemo(() => data?.stats.datas.map((d) => d.data) ?? [], [data])
  // Datas que a camada atual consegue mostrar (o HV so existe nas passagens dual-pol).
  const usable = useMemo(
    () => (data?.stats.datas ?? []).map((d, i) => (layer !== 'hv' || d.tem_hv ? i : -1)).filter((i) => i >= 0),
    [data, layer])
  const fixedDate = layer === 'change' || layer === 'duration'

  // Ao escolher HV numa data sem HV, pula para a data com HV mais proxima.
  useEffect(() => {
    if (usable.length && !usable.includes(dateIdx)) {
      setDateIdx(usable.reduce((a, b) => (Math.abs(b - dateIdx) < Math.abs(a - dateIdx) ? b : a)))
    }
  }, [usable, dateIdx])

  // Pre-carrega as imagens da camada atual para a troca de data e a animacao nao piscarem.
  useEffect(() => {
    if (fixedDate) return
    for (const i of usable) new Image().src = `${DATA}${layer}_${dates[i]}.png`
  }, [dates, usable, layer, fixedDate])

  // Animacao: percorre as datas em loop.
  useEffect(() => {
    if (!playing || usable.length < 2) return
    const id = setInterval(
      () => setDateIdx((i) => usable[(usable.indexOf(i) + 1) % usable.length]),
      usable.length > 6 ? 900 : 1400)
    return () => clearInterval(id)
  }, [playing, usable])

  // Cada cartao da historia ajusta o mapa.
  useEffect(() => {
    if (story === null || !dates.length) return
    const s = STORY[story]
    setPlaying(false)
    setLayer(s.layer)
    setCompare(s.compare)
    setSplit(s.split)
    setDateIdx(s.date === 'first' ? 0 : dates.length - 1)
  }, [story, dates.length])

  if (failed) return <div className="splash">{t.loadError}</div>
  if (!data) return <div className="splash">{t.loading}</div>

  const { stats, cota, optico, bounds } = data
  const n = dates.length
  const date = dates[dateIdx]
  const cur = stats.datas[dateIdx]
  const first = stats.datas[0], last = stats.datas[n - 1]
  const level = (iso: string) => cota.nas_datas_do_radar.find((c) => c.data === iso)?.cota_m ?? null

  const baseUrl = `${DATA}${layer === 'hv' && cur.tem_hv ? 'hv' : 'hh'}_${fixedDate ? last.data : date}.png`
  const overlayUrl =
    layer === 'classes' ? `${DATA}classes_${date}.png`
      : layer === 'change' ? `${DATA}transicao.png`
        : layer === 'duration' ? `${DATA}duracao.png` : null
  const rightLabel = fixedDate
    ? `${t.radar} · ${fmtDate(first.data, lang, false)} → ${fmtDate(last.data, lang)}`
    : `${t.radar} ${layer === 'hv' ? 'HV' : 'HH'} · ${fmtDate(date, lang)}`
  const leftLabel = `${t.optical} · ${fmtDate(optico.data, lang)}`

  const byCount = stats.duracao.km2_por_contagem
  const half = Math.ceil(n / 2)
  const values = {
    n,
    nHv: stats.datas.filter((d) => d.tem_hv).length,
    inc: fmtNum(stats.limiares.incerteza_db, lang, 1),
    opticalDate: fmtDate(optico.data, lang),
    cloud: fmtNum(optico.nuvem_no_recorte_pct, lang),
    floodedFirst: fmtNum(first.km2.floresta_alagada, lang),
    firstDate: fmtDate(first.data, lang, false),
    lastDate: fmtDate(last.data, lang),
    levelFirst: fmtNum(level(first.data) ?? 0, lang, 1),
    levelLast: fmtNum(level(last.data) ?? 0, lang, 1),
    dried: fmtNum(stats.transicao.km2.alagada_para_terra_firme, lang),
    tWater: fmtNum(stats.limiares.usados.agua_aberta_hh_max, lang, 1),
    tFlood: fmtNum(stats.limiares.usados.floresta_alagada_hh_min, lang, 1),
    path: stats.orbita.path,
    frame: stats.orbita.frame,
    k: half,
    r: cota.correlacao ? fmtNum(cota.correlacao.r_pearson, lang, 2) : '',
  }

  const pick = (i: number) => { setPlaying(false); setDateIdx(i) }
  const range = stats.faixa_db_png[layer === 'hv' ? 'hv' : 'hh']
  const curLevel = level(date)

  return (
    <div className={`app${open ? ' panel-open' : ''}`}>
      <main className="stage">
        <CompareMap
          corners={bounds.cantos_lonlat}
          opticalUrl={`${DATA}optico.png`}
          baseUrl={baseUrl}
          overlayUrl={overlayUrl}
          compare={compare}
          split={split}
          onSplit={setSplit}
          leftLabel={leftLabel}
          rightLabel={rightLabel}
          marker={probe?.lngLat ?? null}
          onPick={(ll) => setProbe(probeAt(data, ll))}
        />
        <p className="warning" role="note">{fill(t.warning, values)}</p>

        {story !== null && (
          <section className="card" aria-live="polite">
            <div className="card-step">{story + 1} / {t.cards.length}</div>
            <h2>{t.cards[story].title}</h2>
            <p>{fill(t.cards[story].body, values)}</p>
            <div className="card-nav">
              <button className="btn ghost" onClick={() => setStory(null)}>{t.close}</button>
              <span className="grow" />
              {story > 0 && <button className="btn" onClick={() => setStory(story - 1)}>{t.back}</button>}
              {story < t.cards.length - 1 && (
                <button className="btn primary" onClick={() => setStory(story + 1)}>{t.next}</button>
              )}
            </div>
          </section>
        )}
      </main>

      <aside className="panel">
        <button className="drawer-grip" onClick={() => setOpen(!open)} aria-expanded={open}>
          <span />{t.panelToggle}
        </button>

        <header className="brand">
          <img src={`${import.meta.env.BASE_URL}saramba-icon.svg`} alt="" width={44} height={44} />
          <div>
            <h1>SARamba</h1>
            <p>{t.tagline}</p>
          </div>
          <button className="btn lang" onClick={() => setLang(lang === 'en' ? 'pt' : 'en')}
            aria-label={lang === 'en' ? 'Mudar para português' : 'Switch to English'}>
            {lang === 'en' ? 'PT' : 'EN'}
          </button>
        </header>

        <p className="intro">{t.intro}</p>
        {story === null && (
          <button className="btn primary wide" onClick={() => setStory(0)}>{t.storyStart} →</button>
        )}

        <section>
          <div className="row">
            <h3>{t.timeline}</h3>
            <button className="btn small" disabled={fixedDate} onClick={() => setPlaying(!playing)}>
              {playing ? `❚❚ ${t.pause}` : `▶ ${t.play}`}
            </button>
          </div>
          <p className={`now${fixedDate ? ' off' : ''}`}>
            <strong>{fmtDate(date, lang)}</strong>
            <span className="amber">{t.river} {curLevel !== null ? `${fmtNum(curLevel, lang, 1)} m` : '–'}</span>
            <span className="teal">{fmtNum(cur.km2.floresta_alagada, lang)} km²</span>
          </p>
          <div className="dates" role="group" aria-label={t.timeline}>
            {stats.datas.map((d, i) => (
              <button key={d.data} className={`date${i === dateIdx && !fixedDate ? ' on' : ''}`}
                disabled={fixedDate || !usable.includes(i)} aria-pressed={i === dateIdx} onClick={() => pick(i)}>
                {fmtDate(d.data, lang, false).replace(' de ', ' ').replace('.', '')}
              </button>
            ))}
          </div>
        </section>

        <section>
          <h3>{t.layer}</h3>
          <div className="seg" role="group" aria-label={t.layer}>
            {LAYERS.map((l) => (
              <button key={l} className={l === layer ? 'on' : ''} aria-pressed={l === layer}
                onClick={() => { setLayer(l); if (l === 'change' || l === 'duration') setPlaying(false) }}>
                {t.layers[l]}
              </button>
            ))}
          </div>
          <p className="help">{fill(t.layerHelp[layer], values)}</p>

          {layer === 'classes' && (
            <ul className="legend">
              <li><i style={{ background: '#12C2B0' }} />{t.legend.flooded}<b>{fmtNum(cur.km2.floresta_alagada, lang)} km²</b></li>
              <li><i style={{ background: '#2F7BFF' }} />{t.legend.water}<b>{fmtNum(cur.km2.agua_aberta, lang)} km²</b></li>
              <li><i style={{ background: '#6E7681' }} />{t.legend.land}<b>{fmtNum(cur.km2.terra_firme, lang)} km²</b></li>
            </ul>
          )}
          {layer === 'change' && (
            <ul className="legend">
              <li><i style={{ background: '#FFB020' }} />{t.legend.dried}<b>{fmtNum(stats.transicao.km2.alagada_para_terra_firme, lang)} km²</b></li>
              <li><i style={{ background: '#12C2B0' }} />{t.legend.stillFlooded}<b>{fmtNum(stats.transicao.km2.segue_alagada, lang)} km²</b></li>
              <li><i style={{ background: '#E85D3A' }} />{t.legend.waterGone}<b>{fmtNum(stats.transicao.km2.agua_aberta_recuou, lang)} km²</b></li>
              <li><i style={{ background: '#2F7BFF' }} />{t.legend.newWet}<b>{fmtNum(stats.transicao.km2.passou_a_agua_ou_alagada, lang)} km²</b></li>
            </ul>
          )}
          {layer === 'duration' && (
            <>
              <div className="ramp duration">
                <span>{t.legend.oneDate}</span><div /><span>{fill(t.legend.allDates, values)}</span>
              </div>
              <ul className="legend">
                <li>{t.legend.everFlooded}<b>{fmtNum(stats.duracao.km2_alguma_vez, lang)} km²</b></li>
                <li>{fill(t.legend.mostDates, values)}<b>{fmtNum(byCount.slice(half).reduce((a, b) => a + b, 0), lang)} km²</b></li>
              </ul>
            </>
          )}
          {(layer === 'hh' || layer === 'hv') && (
            <div className="ramp">
              <span>{range[0]} dB</span><div /><span>{range[1]} dB</span>
            </div>
          )}

          <label className="check">
            <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} />
            {t.compare}
            <small>{fmtDate(optico.data, lang, false)} · {fmtNum(optico.nuvem_no_recorte_pct, lang)}% {t.cloud}</small>
          </label>
        </section>

        <section>
          <h3>{t.chartTitle}</h3>
          <LevelChart data={data} lang={lang} t={t} selected={fixedDate ? last.data : date}
            onSelect={(iso) => { const i = dates.indexOf(iso); if (!fixedDate && usable.includes(i)) pick(i) }} />
          <p className="help">{fill(t.chartNote, values)}</p>
          {cota.correlacao && <p className="help">{fill(t.corr, values)}</p>}
        </section>

        <section>
          <div className="row">
            <h3>{t.probeTitle}</h3>
            {probe && <button className="btn small" onClick={() => setProbe(null)}>{t.probeClear}</button>}
          </div>
          {probe ? (
            <>
              <PixelChart probe={probe} stats={stats} lang={lang} t={t} selected={fixedDate ? last.data : date} />
              <p className="help">{fill(t.probeNote, {
                lat: fmtNum(probe.lngLat[1], lang, 3), lon: fmtNum(probe.lngLat[0], lang, 3) })}</p>
            </>
          ) : <p className="help">{t.probeHint}</p>}
        </section>

        <footer>
          <p>{fill(t.method, values)}</p>
          <h3>{t.credits}</h3>
          <p>{t.creditsBody}</p>
          <p>NASA Space Apps Challenge 2026 · “Dancing with the SARs” · MIT License</p>
        </footer>
      </aside>
    </div>
  )
}
