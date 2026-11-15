import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { fill, fmtDate, fmtNum, type Texts } from './i18n'
import type { AppData, Lang } from './types'

interface Props {
  data: AppData
  lang: Lang
  t: Texts
  selected: string
  onSelect: (iso: string) => void
}

const TEAL = '#12C2B0'
const AMBER = '#FFB020'
export const ts = (iso: string) => Date.parse(iso + 'T12:00:00Z')
export const isoOf = (v: number) => new Date(v).toISOString().slice(0, 10)

/**
 * Area de floresta alagada em cada data de radar (eixo esquerdo, com a faixa de incerteza do
 * limiar) contra a cota diaria do rio (eixo direito).
 */
export default function LevelChart({ data, lang, t, selected, onSelect }: Props) {
  const dates = data.stats.datas
  const byDate = new Map(dates.map((d) => [d.data, d]))
  // Mostra a serie de cota de 8 dias antes da primeira cena ate 8 dias depois da ultima.
  const lo = ts(dates[0].data) - 8 * 864e5, hi = ts(dates[dates.length - 1].data) + 8 * 864e5
  const rows = data.cota.serie
    .filter((s) => ts(s.data) >= lo && ts(s.data) <= hi)
    .map((s) => {
      const d = byDate.get(s.data)
      return { t: ts(s.data), iso: s.data, level: s.cota_m, flooded: d?.km2.floresta_alagada, band: d?.floresta_alagada_faixa_km2 }
    })

  // Eixo da cota em multiplos de 5 m; eixo da area ate a centena acima do topo da faixa.
  const levels = rows.map((r) => r.level)
  const levelLo = Math.floor(Math.min(...levels) / 5) * 5
  const levelHi = Math.ceil(Math.max(...levels) / 5) * 5
  const levelTicks = Array.from({ length: (levelHi - levelLo) / 5 + 1 }, (_, i) => levelLo + i * 5)
  const areaHi = Math.ceil(Math.max(...dates.map((d) => d.floresta_alagada_faixa_km2[1])) / 100) * 100
  // Um rotulo de data sim, um nao, para caber.
  const ticks = dates.filter((_, i) => i % 2 === 0).map((d) => ts(d.data))
  const inc = fmtNum(data.stats.limiares.incerteza_db, lang, 1)

  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart
          data={rows}
          margin={{ top: 8, right: 4, bottom: 0, left: -6 }}
          onClick={(e) => {
            const iso = (e?.activePayload?.[0]?.payload as { iso?: string } | undefined)?.iso
            if (!iso) return
            // Vai para a data de radar mais proxima do ponto clicado.
            const nearest = dates.reduce((a, b) =>
              Math.abs(ts(b.data) - ts(iso)) < Math.abs(ts(a.data) - ts(iso)) ? b : a)
            onSelect(nearest.data)
          }}
        >
          <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
          <XAxis
            dataKey="t" type="number" scale="time" domain={[lo, hi]} ticks={ticks}
            tickFormatter={(v) => fmtDate(isoOf(v), lang, false)}
            tick={{ fill: '#A9B8CC', fontSize: 11 }} stroke="rgba(255,255,255,0.2)"
          />
          <YAxis yAxisId="area" tick={{ fill: TEAL, fontSize: 11 }} stroke="transparent" width={44} domain={[0, areaHi]} />
          <YAxis yAxisId="level" orientation="right" tick={{ fill: AMBER, fontSize: 11 }} stroke="transparent"
            width={34} domain={[levelLo, levelHi]} ticks={levelTicks} />
          <Tooltip
            contentStyle={{ background: '#0B1F3A', border: '1px solid rgba(255,255,255,0.18)', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: '#fff' }}
            labelFormatter={(v) => fmtDate(isoOf(v as number), lang)}
            formatter={(value, name) => {
              if (name === 'band') {
                const [a, b] = value as unknown as [number, number]
                return [`${fmtNum(a, lang)}–${fmtNum(b, lang)} km²`, fill(t.chartBand, { inc })]
              }
              return name === 'flooded'
                ? [`${fmtNum(value as number, lang)} km²`, t.legend.flooded]
                : [`${fmtNum(value as number, lang, 2)} m`, t.riverLevel]
            }}
          />
          <ReferenceLine yAxisId="level" x={ts(selected)} stroke="#fff" strokeOpacity={0.55} strokeDasharray="3 3" />
          <Area yAxisId="area" dataKey="band" stroke="none" fill={TEAL} fillOpacity={0.2} connectNulls
            isAnimationActive={false} activeDot={false} />
          <Line yAxisId="level" dataKey="level" stroke={AMBER} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line yAxisId="area" dataKey="flooded" stroke={TEAL} strokeWidth={2.5} connectNulls
            dot={{ r: 4, fill: TEAL, stroke: '#0B1F3A', strokeWidth: 2 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="chart-key">
        <span><i style={{ background: TEAL }} />{t.chartFlooded}</span>
        <span><i style={{ background: TEAL, opacity: 0.35 }} />{fill(t.chartBand, { inc })}</span>
        <span><i style={{ background: AMBER }} />{t.chartLevel}</span>
      </div>
    </div>
  )
}
