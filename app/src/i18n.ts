import type { Lang } from './types'

// Textos da interface. Ingles e o padrao (regra do Space Apps); portugues pelo botao PT/EN.
// Linguagem cautelosa de proposito: "is consistent with", nunca "proves".
const en = {
  tagline: 'The water hidden under the forest',
  intro:
    'NISAR’s L-band radar passes through clouds and forest canopy. Where the forest floor is under water, the signal bounces between water and trunks and comes back very bright.',
  warning:
    'Provisional NISAR products (calibrated, under validation). One season, {n} dates: this shows a trend, not statistical proof.',
  compare: 'Compare with optical',
  layer: 'Radar layer',
  layers: { hh: 'HH', hv: 'HV', classes: 'Classes', duration: 'Duration', change: 'Change' },
  layerHelp: {
    hh: 'HH backscatter. Bright = strong return, consistent with flooded forest. Black = open water.',
    hv: 'HV backscatter. Responds mostly to canopy volume, so flooded and dry forest look alike. Only {nHv} of the {n} passes recorded HV.',
    classes: 'Three classes from HH thresholds calibrated on the histogram of all dates.',
    duration: 'On how many of the {n} dates each pixel was classified as flooded forest. Dark blue stayed flooded longest.',
    change: 'What changed between the first and the last date.',
  },
  timeline: 'Radar date',
  play: 'Play',
  pause: 'Pause',
  riverLevel: 'River level',
  river: 'river',
  legend: {
    flooded: 'Flooded forest',
    water: 'Open water',
    land: 'Not flooded on this date',
    stillFlooded: 'Still flooded',
    dried: 'Flooded forest → not flooded',
    waterGone: 'Open water → exposed',
    newWet: 'Became water or flooded',
    oneDate: '1 date',
    allDates: '{n} dates',
    everFlooded: 'Flooded on at least one date',
    mostDates: 'Flooded on {k} or more dates',
  },
  chartTitle: 'Flooded forest area × Rio Negro level',
  chartFlooded: 'Flooded forest (km²)',
  chartBand: 'threshold ± {inc} dB',
  chartLevel: 'River level at Manaus (m)',
  chartNote:
    'Area inside the 50 × 50 km window. The band shows the same classification with the threshold moved by ± {inc} dB. River level: ANA telemetry, station 14990000, raw daily mean.',
  corr: 'Across the {n} dates, area and river level have r = {r}. Both fall through a single dry season, so a high r is expected; it is not proof.',
  probeTitle: 'HH at the point you clicked',
  probeHint: 'Click anywhere on the radar image to see how HH changed at that point.',
  probeThreshold: 'flooded-forest threshold',
  probeWater: 'open-water threshold',
  probeNote: 'Mean HH of a 160 m cell around the point ({lat}, {lon}).',
  probeClear: 'Clear',
  optical: 'Sentinel-2 optical',
  radar: 'NISAR L-band',
  cloud: 'cloud',
  story: 'Story',
  storyStart: 'Start the story',
  next: 'Next',
  back: 'Back',
  close: 'Explore freely',
  cards: [
    {
      title: 'What optical sees',
      body: 'Sentinel-2, {opticalDate}: {cloud}% of this window is cloud or cloud shadow. Where the ground shows, the islands of Anavilhanas are a uniform green. Nothing tells flooded forest from dry forest.',
    },
    {
      title: 'What NISAR sees',
      body: 'Same day, same place. The radar ignores the clouds. Open water is black; the very bright fringes along islands and creeks are consistent with flooded forest (igapó): about {floodedFirst} km² in this window.',
    },
    {
      title: 'The river recedes',
      body: 'Between {firstDate} and {lastDate} the Rio Negro at Manaus fell from {levelFirst} m to {levelLast} m. Orange marks {dried} km² that were classified as flooded forest and no longer are.',
    },
    {
      title: 'A map of the flood pulse',
      body: 'Stacking all {n} passes shows how long each place stayed flooded. Yellow was flooded only at the peak; dark blue stayed flooded for most of the season. Flooded forests feed fish and store carbon, and NISAR returns every 12 days, cloud or not.',
    },
  ],
  credits: 'Credits',
  creditsBody:
    'NASA-ISRO NISAR L2 GCOV (provisional) via ASF DAAC · ESA Copernicus Sentinel-2 L2A via Earth Search · River level: ANA (Brazilian National Water Agency) · Base map © OpenStreetMap contributors',
  method: 'Thresholds used: open water ≤ {tWater} dB, flooded forest ≥ {tFlood} dB (HH, gamma0). Same orbit on every date: path {path}, frame {frame}.',
  loading: 'Loading data…',
  loadError: 'Could not load the data files in ./data/. Run the pipeline first.',
  panelToggle: 'Details',
}

const pt: typeof en = {
  tagline: 'A água escondida sob a floresta',
  intro:
    'O radar de banda L da NISAR atravessa nuvens e a copa das árvores. Onde o chão da floresta está alagado, o sinal rebate entre a água e os troncos e volta muito forte.',
  warning:
    'Produtos NISAR provisórios (calibrados, em validação). Uma estação, {n} datas: mostra tendência, não prova estatística.',
  compare: 'Comparar com óptico',
  layer: 'Camada de radar',
  layers: { hh: 'HH', hv: 'HV', classes: 'Classes', duration: 'Duração', change: 'Mudança' },
  layerHelp: {
    hh: 'Retroespalhamento HH. Claro = retorno forte, consistente com floresta alagada. Preto = água aberta.',
    hv: 'Retroespalhamento HV. Responde mais ao volume da copa; floresta alagada e seca ficam parecidas. Só {nHv} das {n} passagens gravaram HV.',
    classes: 'Três classes a partir de limiares de HH calibrados no histograma de todas as datas.',
    duration: 'Em quantas das {n} datas cada pixel foi classificado como floresta alagada. Azul-escuro ficou alagado por mais tempo.',
    change: 'O que mudou entre a primeira e a última data.',
  },
  timeline: 'Data do radar',
  play: 'Reproduzir',
  pause: 'Pausar',
  riverLevel: 'Cota do rio',
  river: 'rio',
  legend: {
    flooded: 'Floresta alagada',
    water: 'Água aberta',
    land: 'Não alagado nesta data',
    stillFlooded: 'Continua alagada',
    dried: 'Floresta alagada → não alagada',
    waterGone: 'Água aberta → exposto',
    newWet: 'Virou água ou alagada',
    oneDate: '1 data',
    allDates: '{n} datas',
    everFlooded: 'Alagado em pelo menos uma data',
    mostDates: 'Alagado em {k} ou mais datas',
  },
  chartTitle: 'Área de floresta alagada × cota do Rio Negro',
  chartFlooded: 'Floresta alagada (km²)',
  chartBand: 'limiar ± {inc} dB',
  chartLevel: 'Cota em Manaus (m)',
  chartNote:
    'Área dentro do recorte de 50 × 50 km. A faixa mostra a mesma classificação com o limiar deslocado em ± {inc} dB. Cota: telemetria da ANA, estação 14990000, média diária bruta.',
  corr: 'Nas {n} datas, área e cota têm r = {r}. As duas caem ao longo de uma única vazante, então um r alto é esperado; não é prova.',
  probeTitle: 'HH no ponto clicado',
  probeHint: 'Clique na imagem de radar para ver como o HH mudou naquele ponto.',
  probeThreshold: 'limiar de floresta alagada',
  probeWater: 'limiar de água aberta',
  probeNote: 'HH médio de uma célula de 160 m em torno do ponto ({lat}, {lon}).',
  probeClear: 'Limpar',
  optical: 'Sentinel-2 óptico',
  radar: 'NISAR banda L',
  cloud: 'nuvem',
  story: 'História',
  storyStart: 'Ver a história',
  next: 'Próximo',
  back: 'Voltar',
  close: 'Explorar livremente',
  cards: [
    {
      title: 'O que o óptico vê',
      body: 'Sentinel-2, {opticalDate}: {cloud}% do recorte é nuvem ou sombra de nuvem. Onde o chão aparece, as ilhas de Anavilhanas são um verde uniforme. Nada distingue floresta alagada de floresta seca.',
    },
    {
      title: 'O que a NISAR vê',
      body: 'Mesmo dia, mesmo lugar. O radar ignora as nuvens. Água aberta fica preta; as bordas muito claras de ilhas e igarapés são consistentes com floresta alagada (igapó): cerca de {floodedFirst} km² neste recorte.',
    },
    {
      title: 'O rio recua',
      body: 'Entre {firstDate} e {lastDate} o Rio Negro em Manaus desceu de {levelFirst} m para {levelLast} m. Em laranja, {dried} km² que estavam classificados como floresta alagada e deixaram de estar.',
    },
    {
      title: 'Um mapa do pulso de inundação',
      body: 'Empilhar as {n} passagens mostra por quanto tempo cada lugar ficou alagado. Amarelo só alagou no pico; azul-escuro ficou alagado quase a estação toda. A floresta alagada alimenta peixes e guarda carbono, e a NISAR volta a cada 12 dias, com nuvem ou sem.',
    },
  ],
  credits: 'Créditos',
  creditsBody:
    'NASA-ISRO NISAR L2 GCOV (provisório) via ASF DAAC · ESA Copernicus Sentinel-2 L2A via Earth Search · Cota do rio: ANA (Agência Nacional de Águas e Saneamento Básico) · Mapa base © colaboradores do OpenStreetMap',
  method: 'Limiares usados: água aberta ≤ {tWater} dB, floresta alagada ≥ {tFlood} dB (HH, gamma0). Mesma órbita em todas as datas: path {path}, frame {frame}.',
  loading: 'Carregando dados…',
  loadError: 'Não foi possível carregar os arquivos em ./data/. Rode o pipeline antes.',
  panelToggle: 'Detalhes',
}

export const texts = { en, pt }
export type Texts = typeof en

/** Troca {chave} pelos valores informados. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k) => String(values[k] ?? ''))
}

export function fmtDate(iso: string, lang: Lang, withYear = true): string {
  const d = new Date(iso + 'T12:00:00Z')
  return d.toLocaleDateString(lang === 'pt' ? 'pt-BR' : 'en-GB', {
    day: 'numeric',
    month: 'short',
    ...(withYear ? { year: 'numeric' } : {}),
    timeZone: 'UTC',
  })
}

export function fmtNum(v: number, lang: Lang, digits = 0): string {
  return v.toLocaleString(lang === 'pt' ? 'pt-BR' : 'en-GB', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}
