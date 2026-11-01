import Svg, { Path, Circle, Rect } from 'react-native-svg';
import { colors } from '../theme/tokens';

const paths = {
  wardrobe: 'M4 3h16v18H4z M12 3v18 M8 11v3 M16 11v3',
  grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  sparkle: 'm12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6L12 3 M20 2v4 M18 4h4',
  chat: 'M21 11a9 9 0 0 1-9 9H4l-3 2 2-6a9 9 0 1 1 18-5 M7 10h10 M7 14h6',
  plus: 'M12 5v14 M5 12h14',
  close: 'm6 6 12 12 M6 18 18 6',
  arrow: 'M4 12h16 m-6-6 6 6-6 6',
  back: 'M20 12H4 m6-6-6 6 6 6',
  heart:
    'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z',
  search: 'm16.5 16.5 4.5 4.5',
  filter: 'M4 7h16 M7 12h10 M10 17h4',
  shirt: 'm8 3-6 4 3 5 3-2v11h8V10l3 2 3-5-6-4a4 4 0 0 1-8 0z',
  check: 'm5 12 4 4L19 6',
  camera: 'M3 7h4l2-3h6l2 3h4v14H3z',
  image: 'm3 17 5-5 4 4 3-3 6 6',
  trash: 'M3 6h18 M9 6V3h6v3 M6 6l1 15h10l1-15 M10 10v7 M14 10v7',
  sun: 'M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1 1 M18 18l1 1 M5 19l1-1 M18 6l1-1',
  user: 'M4 21v-2a8 8 0 0 1 16 0v2',
  settings: 'M4 7h16 M4 17h16',
  leaf: 'M20 3C5 2 1 9 5 16c7 7 15 1 15-13z M5 19 16 8',
  send: 'm22 2-7 20-4-9L2 9z M11 13 22 2',
} as const;
export type IconName = keyof typeof paths;

export function Icon({
  name,
  size = 22,
  color = colors.ink,
  filled = false,
}: {
  name: IconName;
  size?: number;
  color?: string;
  filled?: boolean;
}) {
  return (
    <Svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <Path d={paths[name]} fill={filled ? color : 'none'} />
      {name === 'search' && <Circle cx={10.5} cy={10.5} r={7} />}
      {name === 'camera' && <Circle cx={12} cy={13} r={4} />}
      {name === 'sun' && <Circle cx={12} cy={12} r={4} />}
      {name === 'user' && <Circle cx={12} cy={7} r={4} />}
      {name === 'image' && (
        <>
          <Rect x={3} y={3} width={18} height={18} rx={2} />
          <Circle cx={8} cy={8} r={1} />
        </>
      )}
      {name === 'settings' && (
        <>
          <Circle cx={9} cy={7} r={2} />
          <Circle cx={15} cy={17} r={2} />
        </>
      )}
    </Svg>
  );
}
