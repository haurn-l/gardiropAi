import { Redirect } from 'expo-router';
import { clothingApiOrigin } from '../features/wardrobe/data/clothingApi';
import { BottomBarWorkshop } from '../features/workshops/BottomBarWorkshop';

export default function Home() {
  return clothingApiOrigin ? <Redirect href="/clothing-management" /> : <BottomBarWorkshop />;
}
