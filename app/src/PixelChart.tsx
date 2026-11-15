import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtDate, fmtNum, type Texts } from './i18n'
import { isoOf, ts } from './LevelChart'
import type { Lang, Probe, Stats } from './types'

interface Props {
  probe: Probe
  stats: Stats
  lang: Lang
  t: Texts
  selected: string
}

/** HH (dB) do ponto clicado ao longo das datas, com os dois limiares de classificacao. */
export default function PixelChart({ probe, stats, lang, t, selected }: Props) {
  const rows = stats.datas.map((d, i) => ({ t: ts(d.data), db: probe.db[i] }))
  const { agua_aberta_hh_max: tWater, floresta_alagada_hh_min: tFlood } = stats.limiares.usados
  const ticks = stats.datas.filter((_, i) => i % 2 === 0).map((d) => ts(d.data))
  // Eixo ajustado ao ponto: sobre floresta a variacao e de poucos dB e sumiria numa escala fixa.
  const seen = probe.db.filter((v): v is number => v !== null)
  const yLo = Math.max(-24, Math.floor((Math.min(...seen, tFlood) - 2) / 4) * 4)
  const yTicks = Array.from({ length: -yLo / 4 + 1 }, (_, i) => yLo + i * 4)

  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={170}>
        <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
          <XAxis dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']} ticks={ticks}
            tickFormatter={(v) => fmtDate(isoOf(v), lang, false)}
            tick={{ fill: '#A9B8CC', fontSize: 11 }} stroke="rgba(255,255,255,0.2)" />
          <YAxis domain={[yLo, 0]} ticks={yTicks} tick={{ fill: '#A9B8CC', fontSize: 11 }}
            stroke="transparent" width={54} unit=" dB" />
          <Tooltip
            contentStyle={{ background: '#0B1F3A', border: '1px solid rgba(255,255,255,0.18)', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: '#fff' }}
            labelFormatter={(v) => fmtDate(isoOf(v as number), lang)}
            formatter={(v) => [`${fmtNum(v as number, lang, 1)} dB`, 'HH']}
          />
          <ReferenceLine y={tFlood} stroke="#12C2B0" strokeDasharray="4 3" />
          <ReferenceLine y={tWater} stroke="#2F7BFF" strokeDasharray="4 3" />
          <ReferenceLine x={ts(selected)} stroke="#fff" strokeOpacity={0.55} strokeDasharray="3 3" />
          <Line dataKey="db" stroke="#fff" strokeWidth={2} connectNulls isAnimationActive={false}
            dot={{ r: 3.5, fill: '#fff', stroke: '#0B1F3A', strokeWidth: 1.5 }} />
        </LineChart>
      </ResponsiveContainer>
      <div className="chart-key">
        <span><i className="dash" style={{ borderColor: '#12C2B0' }} />{t.probeThreshold}</span>
        <span><i className="dash" style={{ borderColor: '#2F7BFF' }} />{t.probeWater}</span>
      </div>
    </div>
  )
}
