// Formato dos arquivos gerados pelo pipeline em public/data/ (as chaves vem em portugues).

export type Corners = [[number, number], [number, number], [number, number], [number, number]]

export interface Bounds {
  cantos_lonlat: Corners
  largura: number
  altura: number
}

export interface DateStats {
  data: string
  cena: string
  pol: string
  tem_hv: boolean
  km2: { agua_aberta: number; floresta_alagada: number; terra_firme: number; sem_dado: number }
  /** Area de floresta alagada com o limiar mais exigente e menos exigente. */
  floresta_alagada_faixa_km2: [number, number]
}

export interface Stats {
  regiao: string
  orbita: { path: number; frame: number; direcao: string }
  faixa_db_png: { hh: [number, number]; hv: [number, number] }
  limiares: {
    usados: { agua_aberta_hh_max: number; floresta_alagada_hh_min: number }
    incerteza_db: number
  }
  datas: DateStats[]
  transicao: {
    de: string
    ate: string
    km2: {
      segue_alagada: number
      alagada_para_terra_firme: number
      agua_aberta_recuou: number
      passou_a_agua_ou_alagada: number
    }
  }
  duracao: { n_datas: number; km2_por_contagem: number[]; km2_alguma_vez: number }
  serie: { arquivo: string; largura: number; altura: number; fator: number; db_min: number; db_max: number }
}

export interface Cota {
  fonte: string
  estacao: string
  correlacao: { r_pearson: number; n: number } | null
  nas_datas_do_radar: { data: string; cota_m: number | null }[]
  serie: { data: string; cota_m: number }[]
}

export interface Optico {
  data: string
  cenas: string[]
  nuvem_no_recorte_pct: number
}

export interface AppData {
  bounds: Bounds
  stats: Stats
  cota: Cota
  optico: Optico
  /** HH por pixel em resolucao reduzida: uma camada por data (ver stats.serie). */
  serie: Uint8Array
}

export type Layer = 'hh' | 'hv' | 'classes' | 'duration' | 'change'
export type Lang = 'en' | 'pt'

/** Ponto clicado no mapa e sua serie de HH (dB) ao longo das datas. */
export interface Probe {
  lngLat: [number, number]
  db: (number | null)[]
}
