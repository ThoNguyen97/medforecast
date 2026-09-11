import { ComposableMap, Geographies, Geography } from 'react-simple-maps';

// CDN topojson for world countries (lightweight)
const GEO_URL =
  'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json';

interface HotSpot {
  name: string;
  coordinates: [number, number]; // [longitude, latitude]
  level: 'critical' | 'warning';
}

const DEFAULT_HOTSPOTS: HotSpot[] = [
  { name: 'TP.HCM', coordinates: [106.7, 10.78], level: 'critical' },
  { name: 'Hà Nội', coordinates: [105.85, 21.03], level: 'critical' },
  { name: 'Đà Nẵng', coordinates: [108.2, 16.05], level: 'warning' },
];

/**
 * Bản đồ dịch tễ — sử dụng react-simple-maps để render world map đẹp.
 */
export default function EpidemicMapCard({ hotspots = DEFAULT_HOTSPOTS }: { hotspots?: HotSpot[] }) {
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5 h-full flex flex-col">
      <h3 className="font-semibold text-neutral-900 text-base mb-3">Bản đồ dịch tễ</h3>

      <div className="relative bg-blue-50 rounded-2xl overflow-hidden flex-1 min-h-[260px]">
        <ComposableMap
          projection="geoMercator"
          projectionConfig={{
            scale: 110,
            center: [10, 25],
          }}
          width={600}
          height={340}
          style={{ width: '100%', height: '100%' }}
        >
          <Geographies geography={GEO_URL}>
            {({ geographies }: { geographies: any[] }) =>
              geographies.map((geo) => (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  style={{
                    default: {
                      fill: '#e0ecff',
                      stroke: '#bfdbfe',
                      strokeWidth: 0.4,
                      outline: 'none',
                    },
                    hover: {
                      fill: '#cfdcff',
                      outline: 'none',
                    },
                    pressed: { outline: 'none' },
                  }}
                />
              ))
            }
          </Geographies>

          {/* Custom hot-spot markers */}
          {hotspots.map((spot, idx) => (
            <Marker
              key={idx}
              coordinates={spot.coordinates}
              color={spot.level === 'critical' ? '#ef4444' : '#fbbf24'}
              pulse={spot.level === 'critical'}
            />
          ))}
        </ComposableMap>
      </div>

      <div className="flex items-center gap-4 mt-3 text-xs text-neutral-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Nguy hiểm
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-400" /> Cảnh báo
        </span>
      </div>
    </div>
  );
}

import { Marker as RsmMarker } from 'react-simple-maps';

function Marker({
  coordinates,
  color,
  pulse,
}: {
  coordinates: [number, number];
  color: string;
  pulse?: boolean;
}) {
  return (
    <RsmMarker coordinates={coordinates}>
      {pulse && (
        <circle r={9} fill={color} opacity={0.25}>
          <animate
            attributeName="r"
            values="6;14;6"
            dur="2s"
            repeatCount="indefinite"
          />
          <animate
            attributeName="opacity"
            values="0.4;0.05;0.4"
            dur="2s"
            repeatCount="indefinite"
          />
        </circle>
      )}
      <circle r={4.5} fill={color} stroke="white" strokeWidth={1.5} />
    </RsmMarker>
  );
}
