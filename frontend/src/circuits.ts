import austinUrl from './static/assets/cricuits/Austin_9.svg?url'
import catalunyaUrl from './static/assets/cricuits/Catalunya_15.svg?url'
import hungaroringUrl from './static/assets/cricuits/Hungaroring_4.svg?url'
import imolaUrl from './static/assets/cricuits/Imola_6.svg?url'
import interlagosUrl from './static/assets/cricuits/Interlagos_14.svg?url'
import jeddahUrl from './static/assets/cricuits/Jeddah_149.svg?url'
import lasVegasUrl from './static/assets/cricuits/Las_Vegas_152.svg?url'
import lusailUrl from './static/assets/cricuits/Lusail_150.svg?url'
import melbourneUrl from './static/assets/cricuits/Melbourne_10.svg?url'
import mexicoCityUrl from './static/assets/cricuits/Mexico_City_65.svg?url'
import miamiUrl from './static/assets/cricuits/Miami_151.svg?url'
import monteCarloUrl from './static/assets/cricuits/Monte_Carlo_22.svg?url'
import montrealUrl from './static/assets/cricuits/Montreal_23.svg?url'
import monzaUrl from './static/assets/cricuits/Monza_39.svg?url'
import sakhirUrl from './static/assets/cricuits/Sakhir_63.svg?url'
import shanghaiUrl from './static/assets/cricuits/Shanghai_49.svg?url'
import silverstoneUrl from './static/assets/cricuits/Silverstone_2.svg?url'
import spaUrl from './static/assets/cricuits/Spa-Francorchamps_7.svg?url'
import spielbergUrl from './static/assets/cricuits/Spielberg_19.svg?url'
import suzukaUrl from './static/assets/cricuits/Suzuka_46.svg?url'
import yasMarinaUrl from './static/assets/cricuits/Yas_Marina_Circuit_70.svg?url'
import zandvoortUrl from './static/assets/cricuits/Zandvoort_55.svg?url'

export type CircuitKey =
    | 'austin'
    | 'catalunya'
    | 'hungaroring'
    | 'imola'
    | 'interlagos'
    | 'jeddah'
    | 'las_vegas'
    | 'lusail'
    | 'melbourne'
    | 'mexico_city'
    | 'miami'
    | 'monte_carlo'
    | 'montreal'
    | 'monza'
    | 'sakhir'
    | 'shanghai'
    | 'silverstone'
    | 'spa'
    | 'spielberg'
    | 'suzuka'
    | 'yas_marina'
    | 'zandvoort'

export interface CircuitConfig {
    name: string
    svgUrl: string
}

export const CIRCUITS: Record<CircuitKey, CircuitConfig> = {
    austin:       { name: 'Circuit of the Americas', svgUrl: austinUrl },
    catalunya:    { name: 'Circuit de Barcelona-Catalunya', svgUrl: catalunyaUrl },
    hungaroring:  { name: 'Hungaroring', svgUrl: hungaroringUrl },
    imola:        { name: 'Autodromo Enzo e Dino Ferrari', svgUrl: imolaUrl },
    interlagos:   { name: 'Autodromo Jose Carlos Pace', svgUrl: interlagosUrl },
    jeddah:       { name: 'Jeddah Corniche Circuit', svgUrl: jeddahUrl },
    las_vegas:    { name: 'Las Vegas Strip Circuit', svgUrl: lasVegasUrl },
    lusail:       { name: 'Lusail International Circuit', svgUrl: lusailUrl },
    melbourne:    { name: 'Albert Park Circuit', svgUrl: melbourneUrl },
    mexico_city:  { name: 'Autodromo Hermanos Rodriguez', svgUrl: mexicoCityUrl },
    miami:        { name: 'Miami International Autodrome', svgUrl: miamiUrl },
    monte_carlo:  { name: 'Circuit de Monaco', svgUrl: monteCarloUrl },
    montreal:     { name: 'Circuit Gilles Villeneuve', svgUrl: montrealUrl },
    monza:        { name: 'Autodromo Nazionale Monza', svgUrl: monzaUrl },
    sakhir:       { name: 'Bahrain International Circuit', svgUrl: sakhirUrl },
    shanghai:     { name: 'Shanghai International Circuit', svgUrl: shanghaiUrl },
    silverstone:  { name: 'Silverstone Circuit', svgUrl: silverstoneUrl },
    spa:          { name: 'Circuit de Spa-Francorchamps', svgUrl: spaUrl },
    spielberg:    { name: 'Red Bull Ring', svgUrl: spielbergUrl },
    suzuka:       { name: 'Suzuka International Racing Course', svgUrl: suzukaUrl },
    yas_marina:   { name: 'Yas Marina Circuit', svgUrl: yasMarinaUrl },
    zandvoort:    { name: 'Circuit Zandvoort', svgUrl: zandvoortUrl },
}
